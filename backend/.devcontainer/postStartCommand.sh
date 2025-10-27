#!/bin/bash

# Ensure venv is active and dependencies are up to date
workspace_dir=${REMOTE_CONTAINERS_WORKSPACE_FOLDER:-/app}
venv_activate="/usr/src/venvs/app-main/bin/activate"

if [ -d "$workspace_dir/app-main" ] && [ -f "$venv_activate" ]; then
  cd "$workspace_dir/app-main" && source "$venv_activate"
else
  echo "Skipping postStart dependency sync; workspace or venv not found." >&2
  exit 0
fi

git_email=${DEVCONTAINER_GIT_EMAIL:-${DEVCONTAINER_GITHUB_EMAIL:-}}
git_name=${DEVCONTAINER_GIT_NAME:-${DEVCONTAINER_GITHUB_NAME:-}}

if [ -n "$git_email" ] && [ -n "$git_name" ]; then
  git config --global user.email "$git_email"
  git config --global user.name "$git_name"
fi

# Keep the development venv aligned with requirements
pip install -r "$workspace_dir/app-main/requirements.txt" >/dev/null 2>&1 || true

# Optionally run entrypoint tasks manually in dev if needed
# bash /entrypoint.sh
