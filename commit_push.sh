#!/bin/bash

# Script to commit and push changes for Seclorum project
REPO_DIR="/Users/ian/dev/projects/agents/local/seclorum"
FILES=(
    "seclorum/agents/architect.py"
    "seclorum/agents/generator.py"
    "seclorum/agents/developer.py"
    "seclorum/agents/base.py"
    "seclorum/agents/tester.py"
    "examples/3d_game/drone_game.py"
)
COMMIT_MESSAGE="Fix use_remote errors and stabilize drone game pipeline"

# Navigate to repo
cd "$REPO_DIR" || { echo "Error: Cannot access $REPO_DIR"; exit 1; }

# Check if Git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: $REPO_DIR is not a Git repository"
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$CURRENT_BRANCH" ]; then
    echo "Error: Cannot determine current branch"
    exit 1
fi
echo "Current branch: $CURRENT_BRANCH"

# Stage files
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        git add "$file"
        echo "Staged: $file"
    else
        echo "Warning: $file not found"
    fi
done

# Commit
git commit -m "$COMMIT_MESSAGE" || { echo "Error: Commit failed"; exit 1; }
echo "Committed changes: $COMMIT_MESSAGE"

# Check for remote
if git remote | grep -q origin; then
    git push origin "$CURRENT_BRANCH" || { echo "Error: Push failed"; exit 1; }
    echo "Pushed to origin/$CURRENT_BRANCH"
else
    echo "No remote 'origin' found, skipping push"
fi

echo "Done!"
