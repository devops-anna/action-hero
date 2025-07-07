#!/usr/bin/env python3
import os
import sys
import json
import requests
from urllib.parse import quote

if len(sys.argv) != 5:
    print("Usage: import_metadata.py <gitlab_group> <gitlab_host> <github_org> <backup_dir>")
    sys.exit(1)

GL_TOKEN = os.getenv("GL_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
if not GL_TOKEN or not GH_TOKEN:
    print("Both GL_TOKEN and GH_TOKEN must be set")
    sys.exit(1)

gitlab_group = sys.argv[1]
gitlab_host = sys.argv[2]
github_org = sys.argv[3]
backup_dir = sys.argv[4]

headers = {"PRIVATE-TOKEN": GL_TOKEN}

def get_group_path(group):
    url = f"https://{gitlab_host}/api/v4/groups?search={group}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200 or not r.json():
        print("Group not found.")
        sys.exit(1)
    return r.json()[0]["full_path"]

group_path = get_group_path(gitlab_group)

metadata_root = os.path.join(backup_dir, "metadata")
if not os.path.exists(metadata_root):
    print(f"No metadata to import in: {metadata_root}")
    sys.exit(0)

for repo in os.listdir(metadata_root):
    repo_path = os.path.join(metadata_root, repo)
    if not os.path.isdir(repo_path):
        continue

    print(f"\n Importing metadata to {group_path}/{repo}")
    encoded_path = quote(f"{group_path}/{repo}", safe="")
    project_url = f"https://{gitlab_host}/api/v4/projects/{encoded_path}"
    resp = requests.get(project_url, headers=headers)
    if resp.status_code != 200:
        print(f" Project {group_path}/{repo} not found.")
        continue

    project_id = resp.json()["id"]

    milestone_map = {}
    r = requests.get(f"https://{gitlab_host}/api/v4/projects/{project_id}/milestones", headers=headers)
    if r.status_code == 200:
        milestone_map = {m["title"]: m["id"] for m in r.json()}

    # ----- Import Issues -----
    issues_file = os.path.join(repo_path, "issues.json")
    if os.path.exists(issues_file):
        with open(issues_file, "r") as f:
            issues = json.load(f)

        for issue in issues:
            if "pull_request" in issue:
                continue

            github_issue_ref = f"Imported from GitHub issue #{issue['number']}"
            assignees = []
            for assignee in issue.get("assignees", []):
                username = assignee["login"]
                user_search = requests.get(f"https://{gitlab_host}/api/v4/users?username={username}", headers=headers)
                if user_search.status_code == 200 and user_search.json():
                    user_id = user_search.json()[0]["id"]
                    assignees.append(user_id)
                else:
                    print(f" Assignee '{username}' not found in GitLab")
            print(f" Assigning issue to GitLab user IDs: {assignees}")

            search_url = f"https://{gitlab_host}/api/v4/projects/{project_id}/issues?search={quote(str(issue['number']))}"
            search_resp = requests.get(search_url, headers=headers)
            if search_resp.status_code == 200:
                existing_issue = next((i for i in search_resp.json() if github_issue_ref in i.get("description", "")), None)
                if existing_issue:
                    print(f"Issue already exists: {issue['title']}")
                    if assignees:
                        update_resp = requests.put(
                            f"https://{gitlab_host}/api/v4/projects/{project_id}/issues/{existing_issue['iid']}",
                            headers=headers,
                            json={"assignee_ids": assignees}
                        )
                    continue

            labels = [label["name"] for label in issue.get("labels", [])]
            milestone_title = issue.get("milestone", {}).get("title")
            milestone_id = milestone_map.get(milestone_title)

            if milestone_title and milestone_id is None:
                r_milestone = requests.post(
                    f"https://{gitlab_host}/api/v4/projects/{project_id}/milestones",
                    headers=headers,
                    json={"title": milestone_title}
                )
                if r_milestone.status_code == 201:
                    milestone_id = r_milestone.json()["id"]
                    milestone_map[milestone_title] = milestone_id

            description = issue.get("body", "") + f"\n\n_{github_issue_ref}_"
            data = {
                "title": issue["title"],
                "description": description,
                "created_at": issue["created_at"],
                "labels": labels
            }
            if milestone_id:
                data["milestone_id"] = milestone_id
            if assignees:
                data["assignee_ids"] = assignees

            r = requests.post(f"https://{gitlab_host}/api/v4/projects/{project_id}/issues", headers=headers, json=data)
            if r.status_code == 201:
                issue_id = r.json()["iid"]
                print(f" Issue created: {data['title']}")
                for comment in issue.get("comments", []):
                    note_data = {
                        "body": comment.get("body", ""),
                        "created_at": comment.get("created_at"),
                    }
                    r_note = requests.post(
                        f"https://{gitlab_host}/api/v4/projects/{project_id}/issues/{issue_id}/notes",
                        headers=headers,
                        json=note_data
                    )
                if issue.get("state") == "closed":
                    requests.put(
                        f"https://{gitlab_host}/api/v4/projects/{project_id}/issues/{issue_id}",
                        headers=headers,
                        json={"state_event": "close"}
                    )

    pr_file = os.path.join(repo_path, "pull_requests.json")
    if os.path.exists(pr_file):
        with open(pr_file, "r") as f:
            pull_requests = json.load(f)

        local_repo_path = os.path.join(backup_dir, "repos", repo)
        if not os.path.exists(local_repo_path):
            print(f" Cloning missing repo: {repo}")
            os.makedirs(os.path.join(backup_dir, "repos"), exist_ok=True)
            clone_url = f"https://github.com/{github_org}/{repo}.git"
            result = os.system(f"git clone --mirror {clone_url} {local_repo_path}")
            if result != 0:
                print(f" Failed to clone GitHub repo {repo}, skipping MRs.")
                continue

            os.system(f"git -C {local_repo_path} config --global --add safe.directory {os.path.abspath(local_repo_path)}")
            gitlab_url = f"https://oauth2:{GL_TOKEN}@{gitlab_host}/{group_path}/{repo}.git"
            os.system(f"git -C {local_repo_path} remote add gitlab {gitlab_url}")
            os.system(f"git -C {local_repo_path} push --mirror gitlab")

        for pr in pull_requests:
            github_pr_ref = f"Imported from GitHub PR #{pr['number']}"
            search_url = f"https://{gitlab_host}/api/v4/projects/{project_id}/merge_requests?search={quote(str(pr['number']))}"
            search_resp = requests.get(search_url, headers=headers)
            if search_resp.status_code == 200:
                if any(github_pr_ref in mr.get("description", "") for mr in search_resp.json()):
                    print(f" Merge Request already exists: {pr['title']}")
                    continue

            source_branch = pr.get("head", {}).get("ref", "main")
            source_sha = pr.get("head", {}).get("sha")
            target_branch = pr.get("base", {}).get("ref", "main")
            target_sha = pr.get("base", {}).get("sha")

            os.system(f"git -C {local_repo_path} branch -f {source_branch} {source_sha}")
            os.system(f"git -C {local_repo_path} branch -f {target_branch} {target_sha}")
            os.system(f"git -C {local_repo_path} push gitlab {source_branch}:{source_branch}")
            os.system(f"git -C {local_repo_path} push gitlab {target_branch}:{target_branch}")

            description = pr.get("body", "") + f"\n\n_{github_pr_ref}_"
            data = {
                "title": pr["title"],
                "description": description,
                "created_at": pr["created_at"],
                "source_branch": source_branch,
                "target_branch": target_branch,
                "remove_source_branch": False,
                "allow_collaboration": True
            }

            assignees = []
            assignee = pr.get("assignee")
            if assignee:
                username = assignee["login"]
                user_search = requests.get(f"https://{gitlab_host}/api/v4/users?search={username}", headers=headers)
                if user_search.status_code == 200:
                    matched_user = next((u for u in user_search.json() if u.get("username") == username), None)
                    if matched_user:
                        user_id = matched_user["id"]
                        assignees.append(user_id)
                if assignees:
                    data["assignee_ids"] = assignees

            r = requests.post(f"https://{gitlab_host}/api/v4/projects/{project_id}/merge_requests", headers=headers, json=data)
            if r.status_code == 201:
                mr_iid = r.json()["iid"]
                print(f" Merge Request created: {pr['title']}")
                for comment in pr.get("comments", []):
                    note_data = {
                        "body": comment.get("body", ""),
                        "created_at": comment.get("created_at"),
                    }
                    r_note = requests.post(
                        f"https://{gitlab_host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes",
                        headers=headers,
                        json=note_data
                    )
                if pr.get("state") == "closed":
                    requests.put(
                        f"https://{gitlab_host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}",
                        headers=headers,
                        json={"state_event": "close"}
                    )
            else:
                print(f" Failed to create MR for: {pr['title']} — {r.status_code}: {r.text}")
