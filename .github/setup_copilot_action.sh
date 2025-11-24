#!/bin/bash

# --- CONFIGURATION ---
ORG="HyperionGray"     # Change to your org name
REPO=".github"         # Central workflows repo
GH_WORKFLOW_DIR=".github/workflows"
WORKFLOW_FILES=(auto-copilot-org-playwright-loopv2.yml workflows-sync.yml)   # List workflow files to add

# --- 1. Install GitHub CLI ---
echo "Updating package list and installing gh..."
sudo apt update
sudo apt install -y gh

# --- 2. Authenticate with GitHub CLI using OAuth (browser-based) ---
echo "Authenticating gh CLI via OAuth..."
gh auth login --hostname github.com --git-protocol https

# --- 3. Clone the .github repo ---
echo "Cloning $ORG/$REPO ..."
git clone "https://github.com/$ORG/$REPO.git"
cd "$REPO"

# --- 4. Add workflow files ---
mkdir -p "$GH_WORKFLOW_DIR"
for wf in "${WORKFLOW_FILES[@]}" ; do
    # Check for local files to copy in the parent directory.
    if [ -f "../$wf" ]; then
        cp "../$wf" "$GH_WORKFLOW_DIR/$wf"
        echo "Copied $wf to $GH_WORKFLOW_DIR/"
    else
        echo "# Placeholder workflow for $wf" > "$GH_WORKFLOW_DIR/$wf"
        echo "Created placeholder for $wf in $GH_WORKFLOW_DIR/"
    fi
done

git add "$GH_WORKFLOW_DIR"
git commit -m "Add auto-assign and workflow sync actions"
git push

echo "Workflows added and pushed to $ORG/$REPO."
