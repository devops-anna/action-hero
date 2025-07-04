#!/bin/bash
set -e
set -x  

GL_GROUP=$1
GL_HOST=$2
PROJECT_NAME=$3 

if [ -z "$GL_TOKEN" ]; then
  echo "Error: GL_TOKEN env variable not set"
  exit 1
fi

if [ -z "$GL_GROUP" ] || [ -z "$GL_HOST" ]; then
  echo "Usage: import_to_gitlab.sh <gitlab_group> <gitlab_host> [project_name]"
  exit 1
fi

echo "Importing repos to GitLab group: $GL_GROUP at host: $GL_HOST"

cd backup

GL_GROUP_INFO=$(curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" "https://$GL_HOST/api/v4/groups?search=$GL_GROUP" | jq '.[0]')
namespace_id=$(echo "$GL_GROUP_INFO" | jq '.id')
namespace_path=$(echo "$GL_GROUP_INFO" | jq -r '.full_path')

if [ -z "$namespace_id" ] || [ "$namespace_id" = "null" ]; then
  echo "Error: GitLab group $GL_GROUP not found"
  exit 1
fi

process_repo() {
  local repo_name=$1
  local repo_dir="$repo_name.git"

  if [ ! -d "$repo_dir" ]; then
    echo "Repo directory $repo_dir not found"
    return
  fi

  echo "Processing repo: $repo_name"
  project_path_urlencoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$namespace_path/$repo_name', safe=''))")

  status_code=$(curl -s -o /dev/null -w "%{http_code}" --header "PRIVATE-TOKEN: $GL_TOKEN" \
    "https://$GL_HOST/api/v4/projects/$project_path_urlencoded")

  if [ "$status_code" == "404" ]; then
    echo "Creating project $repo_name under $GL_GROUP"
    curl -s --request POST --header "PRIVATE-TOKEN: $GL_TOKEN" \
      --data "name=$repo_name&namespace_id=$namespace_id" \
      "https://$GL_HOST/api/v4/projects"
  else
    echo "Project $repo_name already exists"
  fi

  remote_url="https://oauth2:$GL_TOKEN@$GL_HOST/$namespace_path/$repo_name.git"
  git --git-dir="$repo_dir" push --mirror "$remote_url" || { echo "Git push failed for $repo_name"; exit 1; }
  cd "$repo_dir"
  git lfs push --all "$remote_url" || echo "No LFS content to push for $repo_name"
  cd ..
}

if [ -n "$PROJECT_NAME" ]; then
  process_repo "$PROJECT_NAME"
else
  for repo_dir in *.git; do
    repo_name="${repo_dir%.git}"
    process_repo "$repo_name"
  done
fi

echo "Import completed!"
