#!/bin/bash
set -e

GL_GROUP=$1
GL_HOST=$2

if [ -z "$GL_TOKEN" ]; then
  echo "Error: GL_TOKEN env variable not set"
  exit 1
fi

if [ -z "$GL_GROUP" ] || [ -z "$GL_HOST" ]; then
  echo "Usage: import_to_gitlab.sh <gitlab_group> <gitlab_host>"
  exit 1
fi

echo "Importing repos to GitLab group: $GL_GROUP at host: $GL_HOST"

cd backup


GL_GROUP_INFO=$(curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" "https://$GL_HOST/api/v4/groups?search=$GL_GROUP" | jq '.[0]')
namespace_id=$(echo "$GL_GROUP_INFO" | jq '.id')
namespace_path=$(echo "$GL_GROUP_INFO" | jq -r '.full_path')

for repo_dir in *.git; do
  [ -d "$repo_dir" ] || continue

  repo_name="${repo_dir%.git}"
  echo "Processing repo: $repo_name"

  # Create project in GitLab if doesn't exist
  # Using GitLab API to create project under the group

  # Check if project exists
  status_code=$(curl -s -o /dev/null -w "%{http_code}" --header "PRIVATE-TOKEN: $GL_TOKEN" \
    "https://$GL_HOST/api/v4/projects/$GL_GROUP%2F$repo_name")
  namespace_id=$(curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" "https://$GL_HOST/api/v4/groups?search=$GL_GROUP" | jq '.[0].id')
  if [ "$status_code" == "404" ]; then
    echo "Creating project $repo_name under $GL_GROUP with namespace ID $namespace_id"
    curl -s --request POST --header "PRIVATE-TOKEN: $GL_TOKEN" \
      --data "name=$repo_name&namespace_id=$namespace_id"\
      "https://$GL_HOST/api/v4/projects"
  else
    echo "Project $repo_name already exists"
  fi

  # Push repo mirror to GitLab
  echo "Pushing $repo_name to GitLab ..."
  git --git-dir="$repo_dir" push --mirror "https://oauth2:$GL_TOKEN@$GL_HOST/$namespace_path/$repo_name.git"
done

echo "Import completed!"
