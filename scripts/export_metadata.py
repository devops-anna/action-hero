#!/usr/bin/env python3
import os
import sys
import json
import requests
import time

if len(sys.argv) != 3:
    print("Usage: export_metadata.py <github_org> <repo_name>")
    sys.exit(1)

GH_TOKEN = os.getenv("GH_TOKEN")
if not GH_TOKEN:
    print("GH_TOKEN not set")
    sys.exit(1)

org = sys.argv[1]
repo = sys.argv[2]
headers = {"Authorization": f"Bearer {GH_TOKEN}"}
backup_dir = f"metadata/{repo}"
os.makedirs(backup_dir, exist_ok=True)

print(f"Exporting metadata from {repo}...")

# Export issues (excluding PRs)
issues_url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page=100"
issues = []
while issues_url:
    resp = requests.get(issues_url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch issues: {resp.text}")
        break

    page_items = resp.json()
    filtered_issues = [issue for issue in page_items if "pull_request" not in issue]

    # For each issue, fetch comments
    for issue in filtered_issues:
        comments_url = issue["comments_url"]
        comments = []
        while comments_url:
            c_resp = requests.get(comments_url, headers=headers)
            if c_resp.status_code != 200:
                print(f"Failed to fetch comments for issue {issue['number']}: {c_resp.text}")
                break
            comments.extend(c_resp.json())
            # Pagination for comments
            if 'next' in c_resp.links:
                comments_url = c_resp.links['next']['url']
            else:
                comments_url = None
            # To avoid rate limits
            time.sleep(0.1)
        issue["comments"] = comments

    issues.extend(filtered_issues)

    # Pagination for issues
    if 'next' in resp.links:
        issues_url = resp.links['next']['url']
    else:
        issues_url = None

with open(f"{backup_dir}/issues.json", "w") as f:
    json.dump(issues, f, indent=2)

print(f"Exported {len(issues)} issues with comments.")
