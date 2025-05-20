#!/usr/bin/env python3
import os
import sys
import json
import requests

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

# Export issues
issues_url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page=100"
issues = []
while issues_url:
    resp = requests.get(issues_url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch issues: {resp.text}")
        break
    issues.extend(resp.json())
    # Pagination
    if 'next' in resp.links:
        issues_url = resp.links['next']['url']
    else:
        issues_url = None

with open(f"{backup_dir}/issues.json", "w") as f:
    json.dump(issues, f, indent=2)

print(f"Exported {len(issues)} issues.")
