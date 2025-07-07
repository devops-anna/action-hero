#!/bin/bash
set -e

GL_GROUP="$1"
GL_HOST="$2"
BACKUP_DIR="$3"

if [ -z "$GL_GROUP" ] || [ -z "$GL_HOST" ] || [ -z "$BACKUP_DIR" ]; then
  echo "Usage: import_gitlab.sh <gitlab_group> <gitlab_host> <backup_dir>"
  exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
  echo "Error: Backup directory '$BACKUP_DIR' not found. Ensure export step completed successfully."
  exit 1
fi

if [ ! -d "$BACKUP_DIR/repos" ]; then
  echo "Error: '$BACKUP_DIR/repos' directory not found. No repos to import."
  exit 1
fi

echo "Importing repositories from: $BACKUP_DIR/repos"

for repo_path in "$BACKUP_DIR/repos"/*.git; do
  repo_name=$(basename "$repo_path" .git)
  echo "Processing repository: $repo_name"

  # Create project on GitLab (ignore if it already exists)
  echo "Creating project $GL_GROUP/$repo_name on $GL_HOST (if not exists)..."
  create_response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://$GL_HOST/api/v4/projects" \
    --header "PRIVATE-TOKEN: $GL_TOKEN" \
    --data "name=$repo_name&namespace_id=$(curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" "https://$GL_HOST/api/v4/groups/$GL_GROUP" | jq '.id')")

  if [ "$create_response" = "201" ]; then
    echo "✔️ Created project $repo_name"
  else
    echo "ℹ️ Project $repo_name may already exist or failed to create (HTTP $create_response)"
  fi

  # Push repo to GitLab
  gitlab_url="https://oauth2:$GL_TOKEN@$GL_HOST/$GL_GROUP/$repo_name.git"

  echo "Pushing $repo_name to GitLab..."
  git -C "$repo_path" remote set-url origin "$gitlab_url" || git -C "$repo_path" remote add origin "$gitlab_url"
  git -C "$repo_path" push --mirror origin

  echo "✅ Finished importing $repo_name"
done
