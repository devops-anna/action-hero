#!/bin/bash
set -e
set -x

ORG=$1
REPOS_INPUT=$2

echo "Exporting repos from GitHub org: $ORG"

if [ -z "$GH_TOKEN" ]; then
  echo "Error: GH_TOKEN env variable not set"
  exit 1
fi

mkdir -p backup
cd backup

clone_repo() {
  local repo_name="$1"
  echo "Cloning $repo_name ..."
  git clone --mirror "https://x-access-token:$GH_TOKEN@github.com/$ORG/$repo_name.git" "$repo_name.git"
  # LFS fetch
  cd "$repo_name.git"
  git lfs fetch --all || echo "No LFS content found for $repo_name"
  cd ..
}

if [ -z "$REPOS_INPUT" ]; then
  echo "No specific repos provided, fetching all repos from organization..."
  page=1
  per_page=100
  repos=()

  while true; do
    response=$(curl -s -H "Authorization: token $GH_TOKEN" \
      "https://api.github.com/orgs/$ORG/repos?per_page=$per_page&page=$page")
    repo_names=$(echo "$response" | jq -r '.[].name')
    if [ -z "$repo_names" ]; then
      break
    fi
    repos+=($repo_names)
    if [ $(echo "$response" | jq length) -lt $per_page ]; then
      break
    fi
    ((page++))
  done

  if [ ${#repos[@]} -eq 0 ]; then
    echo "No repos found in organization $ORG"
    exit 1
  fi

  for repo in "${repos[@]}"; do
    clone_repo "$repo"
  done
else
  IFS=',' read -ra repos <<< "$REPOS_INPUT"
  for repo in "${repos[@]}"; do
    clone_repo "$repo"
  done
fi

echo "All repos cloned successfully!"
