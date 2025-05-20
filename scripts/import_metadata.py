#!/usr/bin/env python3
import os
import sys
import json
import requests
from urllib.parse import quote

if len(sys.argv) != 3:
    print("Usage: import_metadata.py <gitlab_group> <gitlab_host>")
    sys.exit(1)

GL_TOKEN = os.getenv("GL_TOKEN")
if not GL_TOKEN:
    print("GL_TOKEN not set")
    sys.exit(1)

group = sys.argv[1]
host = sys.argv[2]
headers = {"PRIVATE-TOKEN": GL_TOKEN}

def get_group_path(group):
    url = f"https://{host}/api/v4/groups?search={group}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200 or not r.json():
        print("Group not found.")
        sys.exit(1)
    return r.json()[0]["full_path"]

group_path = get_group_path(group)

metadata_root = "metadata"
if not os.path.exists(metadata_root):
    print("No metadata to import.")
    sys.exit(0)

for repo in os.listdir(metadata_root):
    repo_path = os.path.join(metadata_root, repo)
    if not os.path.isdir(repo_path):
        continue

    print(f"Importing metadata to {group_path}/{repo}...")
    encoded_path = quote(f"{group_path}/{repo}", safe="")
    project_url = f"https://{host}/api/v4/projects/{encoded_path}"
    resp = requests.get(project_url, headers=headers)
    if resp.status_code != 200:
        print(f"Project {group_path}/{repo} not found.")
        continue

    project_id = resp.json()["id"]

    # Fetch milestone mapping
    milestone_map = {}
    r = requests.get(f"https://{host}/api/v4/projects/{project_id}/milestones", headers=headers)
    if r.status_code == 200:
        milestone_map = {m["title"]: m["id"] for m in r.json()}

    issues_file = os.path.join(repo_path, "issues.json")
    if not os.path.exists(issues_file):
        print(f"No issues file for {repo}")
        continue

    with open(issues_file, "r") as f:
        issues = json.load(f)

    for issue in issues:
        if "pull_request" in issue:
            continue

        labels = [label["name"] for label in issue.get("labels", [])]
        milestone_title = issue.get("milestone")["title"] if issue.get("milestone") else None
        milestone_id = milestone_map.get(milestone_title)

        # Create milestone if needed
        if milestone_title and milestone_id is None:
            milestone_data = {"title": milestone_title}
            r_milestone = requests.post(
                f"https://{host}/api/v4/projects/{project_id}/milestones",
                headers=headers,
                json=milestone_data
            )
            if r_milestone.status_code == 201:
                milestone_id = r_milestone.json()["id"]
                milestone_map[milestone_title] = milestone_id
                print(f"Created milestone '{milestone_title}' with ID {milestone_id}")
            else:
                print(f"Failed to create milestone '{milestone_title}': {r_milestone.status_code} {r_milestone.text}")

        # Prepare issue data
        data = {
            "title": issue["title"],
            "description": issue.get("body", ""),
            "created_at": issue["created_at"],
            "labels": labels
        }

        if milestone_id:
            data["milestone_id"] = milestone_id

        # Map assignees
        assignees = []
        for assignee in issue.get("assignees", []):
            username = assignee["login"]
            user_search = requests.get(f"https://{host}/api/v4/users?username={username}", headers=headers)
            if user_search.status_code == 200 and user_search.json():
                user_id = user_search.json()[0]["id"]
                assignees.append(user_id)

        if assignees:
            data["assignee_ids"] = assignees

        # Create issue
        r = requests.post(f"https://{host}/api/v4/projects/{project_id}/issues", headers=headers, json=data)
        if r.status_code == 201:
            issue_id = r.json()["iid"]
            print(f"Issue created: {data['title']}")

            # Add comments
            for comment in issue.get("comments", []):
                note_data = {
                    "body": comment.get("body", ""),
                    "created_at": comment.get("created_at"),
                }
                r_note = requests.post(
                    f"https://{host}/api/v4/projects/{project_id}/issues/{issue_id}/notes",
                    headers=headers,
                    json=note_data
                )
                if r_note.status_code == 201:
                    print(f"  Imported comment: {note_data['body'][:30]}...")
                else:
                    print(f"  Failed to import comment: {r_note.status_code} {r_note.text}")

            # Close issue if originally closed
            if issue.get("state") == "closed":
                close_url = f"https://{host}/api/v4/projects/{project_id}/issues/{issue_id}"
                close_resp = requests.put(close_url, headers=headers, json={"state_event": "close"})
                if close_resp.status_code == 200:
                    print(f"Issue closed: {data['title']}")
                else:
                    print(f"Failed to close issue: {data['title']} — {close_resp.status_code} {close_resp.text}")
        else:
            print(f"Failed to create issue: {data['title']} — {r.status_code} {r.text}")
