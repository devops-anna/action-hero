#!/bin/bash
set -e
set -x

GL_GROUP=$1
GL_HOST=$2
PROJECT_NAME=$3

# Check GitLab token
if [ -z "$GL_TOKEN" ]; then
  echo "Error: GL_TOKEN env variable not set"
  exit 1
fi

# Validate inputs
if [ -z "$GL_GROUP" ] || [ -z "$GL_HOST" ]; then
  echo "Usage: import_gitlab.sh <gitlab_group> <gitlab_host> [project_name]"
  exit 1
fi

# Validate backup directory
if [ ! -d "backup" ]; then
  echo "Error: 'backup' directory not found. Ensure export step completed successfully."
  exit 1
fi

cd backup

# Fetch GitLab group info
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
    echo "⚠️ Repo directory $repo_dir not found — skipping"
    return
  fi

  echo "🔄 Processing repo: $repo_name"
  project_path_urlencoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${namespace_path}/${repo_name}', safe=''))")

  # Check if project exists
  status_code=$(curl -s -o /dev/null -w "%{http_code}" --header "PRIVATE-TOKEN: $GL_TOKEN" \
    "https://$GL_HOST/api/v4/projects/$project_path_urlencoded")

  # Create project if not exists
  if [ "$status_code" == "404" ]; then
    echo "📦 Creating project $repo_name under $GL_GROUP"
    create_response=$(curl -s -w "%{http_code}" --output /tmp/create_response.json --request POST \
      --header "PRIVATE-TOKEN: $GL_TOKEN" \
      --data "name=$repo_name&namespace_id=$namespace_id" \
      "https://$GL_HOST/api/v4/projects")

    create_code="${create_response: -3}"
    if [ "$create_code" != "200" ] && [ "$create_code" != "201" ]; then
      echo "❌ Failed to create project $repo_name. API response:"
      cat /tmp/create_response.json
      exit 1
    fi
  else
    echo "✅ Project $repo_name alread_
