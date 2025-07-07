#!/usr/bin/env python3
import os
import sys
import json
import requests
import time

def get_paginated_data(url, headers, delay=0.2):
    items = []
    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch {url}: {resp.text}")
            break
        items.extend(resp.json())
        url = resp.links.get('next', {}).get('url')
        time.sleep(delay)
    return items

# --- Input Validation ---
if len(sys.argv) != 4:
    print("Usage: export_metadata.py <github_org> <repo_name> <backup_dir>")
    sys.exit(1)

org = sys.argv[1]
repo = sys.argv[2]
base_backup_dir = sys.argv[3]
repo_backup_dir = os.path.join(base_backup_dir, repo)
os.makedirs(repo_backup_dir, exist_ok=True)

# --- Authentication ---
GH_TOKEN = os.getenv("GH_TOKEN")
if not GH_TOKEN:
    print("GH_TOKEN not set")
    sys.exit(1)

headers = {"Authorization": f"Bearer {GH_TOKEN}"}

print(f"\n🔁 Exporting metadata from GitHub repo: {org}/{repo}")

# --- Export Issues (excluding PRs) ---
print("📝 Exporting issues with comments and labels...")
issues_url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page=100"
all_issues = []

while issues_url:
    resp = requests.get(issues_url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch issues: {resp.text}")
        break

    page_issues = resp.json()
    real_issues = [i for i in page_issues if "pull_request" not in i]

    for issue in real_issues:
        # Fetch comments
        comments = get_paginated_data(issue["comments_url"], headers, delay=0.1)
        issue["comments"] = comments

    all_issues.extend(real_issues)
    issues_url = resp.links.get('next', {}).get('url')
    time.sleep(0.2)

with open(f"{repo_backup_dir}/issues.json", "w") as f:
    json.dump(all_issues, f, indent=2)
print(f"✅ Exported {len(all_issues)} issues with comments.")

# --- Export Pull Requests ---
print("🔀 Exporting pull requests with comments, reviewers, files, and commits...")
pulls_url = f"https://api.github.com/repos/{org}/{repo}/pulls?state=all&per_page=100"
pull_requests = []

while pulls_url:
    resp = requests.get(pulls_url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch pull requests: {resp.text}")
        break

    page_pulls = resp.json()

    for pr in page_pulls:
        pr_number = pr["number"]

        # Issue comments
        issue_comments_url = f"https://api.github.com/repos/{org}/{repo}/issues/{pr_number}/comments"
        pr["comments"] = get_paginated_data(issue_comments_url, headers)

        # Review comments
        review_comments_url = f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}/comments"
        pr["review_comments"] = get_paginated_data(review_comments_url, headers)

        # Reviewers
        reviewers_url = f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}/requested_reviewers"
        r_resp = requests.get(reviewers_url, headers=headers)
        pr["reviewers"] = r_resp.json().get("users", []) if r_resp.status_code == 200 else []

        # Files changed
        files_url = f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}/files"
        pr["files"] = get_paginated_data(files_url, headers)

        # Commits in PR
        commits_url = f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}/commits"
        pr["commits"] = get_paginated_data(commits_url, headers)

        pull_requests.append(pr)

    pulls_url = resp.links.get('next', {}).get('url')
    time.sleep(0.2)

with open(f"{repo_backup_dir}/pull_requests.json", "w") as f:
    json.dump(pull_requests, f, indent=2)
print(f"✅ Exported {len(pull_requests)} pull requests.")

# --- Export Repo Labels ---
print("🏷️ Exporting repository labels...")
labels_url = f"https://api.github.com/repos/{org}/{repo}/labels?per_page=100"
labels = get_paginated_data(labels_url, headers)
with open(f"{repo_backup_dir}/labels.json", "w") as f:
    json.dump(labels, f, indent=2)
print(f"✅ Exported {len(labels)} labels.")

# --- Export Milestones ---
print("📅 Exporting milestones...")
milestones_url = f"https://api.github.com/repos/{org}/{repo}/milestones?state=all&per_page=100"
milestones = get_paginated_data(milestones_url, headers)
with open(f"{repo_backup_dir}/milestones.json", "w") as f:
    json.dump(milestones, f, indent=2)
print(f"✅ Exported {len(milestones)} milestones.")

print("\n🎉 Metadata export completed for", repo)
