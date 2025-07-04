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

print(f"\n Exporting metadata from GitHub repo: {org}/{repo}")
print("\n Exporting issues...")
issues_url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page=100"
issues = []

while issues_url:
    resp = requests.get(issues_url, headers=headers)
    if resp.status_code != 200:
        print(f" Failed to fetch issues: {resp.text}")
        break

    page_items = resp.json()
    filtered_issues = [issue for issue in page_items if "pull_request" not in issue]

    for issue in filtered_issues:
        comments_url = issue["comments_url"]
        comments = []
        while comments_url:
            c_resp = requests.get(comments_url, headers=headers)
            if c_resp.status_code != 200:
                print(f" Failed to fetch comments for issue #{issue['number']}: {c_resp.text}")
                break
            comments.extend(c_resp.json())
            comments_url = c_resp.links.get('next', {}).get('url')
            time.sleep(0.1)
        issue["comments"] = comments

    issues.extend(filtered_issues)
    issues_url = resp.links.get('next', {}).get('url')
    time.sleep(0.2)

with open(f"{backup_dir}/issues.json", "w") as f:
    json.dump(issues, f, indent=2)
print(f"Exported {len(issues)} issues with comments.")

print("\n Exporting pull requests...")
pulls_url = f"https://api.github.com/repos/{org}/{repo}/pulls?state=all&per_page=100"
pull_requests = []

while pulls_url:
    resp = requests.get(pulls_url, headers=headers)
    if resp.status_code != 200:
        print(f" Failed to fetch pull requests: {resp.text}")
        break

    page_pulls = resp.json()

    for pr in page_pulls:
        pr_number = pr["number"]

        issue_comments_url = f"https://api.github.com/repos/{org}/{repo}/issues/{pr_number}/comments"
        issue_comments = []
        ic_resp = requests.get(issue_comments_url, headers=headers)
        if ic_resp.status_code == 200:
            issue_comments = ic_resp.json()
        pr["comments"] = issue_comments

        review_comments_url = f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}/comments"
        review_comments = []
        rc_resp = requests.get(review_comments_url, headers=headers)
        if rc_resp.status_code == 200:
            review_comments = rc_resp.json()
        pr["review_comments"] = review_comments

        pull_requests.append(pr)

    pulls_url = resp.links.get('next', {}).get('url')
    time.sleep(0.2)

with open(f"{backup_dir}/pull_requests.json", "w") as f:
    json.dump(pull_requests, f, indent=2)
print(f" Exported {len(pull_requests)} pull requests with comments.")
