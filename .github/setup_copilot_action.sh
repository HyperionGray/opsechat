#!/usr/bin/env bash

set -euo pipefail

# --- CONFIGURATION ---
ORG="${ORG:-HyperionGray}"
REPO="${REPO:-.github}"
GH_WORKFLOW_DIR="${GH_WORKFLOW_DIR:-.github/workflows}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${TEMPLATE_DIR:-$SCRIPT_DIR/workflow-templates}"
WORKFLOW_FILES=(auto-copilot-playwright-auto-test.yml workflows-sync.yml)

if ! command -v gh >/dev/null 2>&1; then
    echo "gh CLI is required but not installed."
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "git is required but not installed."
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo "gh CLI is not authenticated. Run: gh auth login"
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Cloning $ORG/$REPO into temporary workspace..."
git clone "https://github.com/$ORG/$REPO.git" "$WORKDIR/$REPO"

TARGET_DIR="$WORKDIR/$REPO/$GH_WORKFLOW_DIR"
mkdir -p "$TARGET_DIR"

for wf in "${WORKFLOW_FILES[@]}"; do
    SOURCE_FILE="$TEMPLATE_DIR/$wf"
    if [ ! -f "$SOURCE_FILE" ]; then
        echo "Missing required workflow template: $SOURCE_FILE"
        exit 1
    fi
    cp "$SOURCE_FILE" "$TARGET_DIR/$wf"
    echo "Synced $wf to $GH_WORKFLOW_DIR/"
done

cd "$WORKDIR/$REPO"
git add "$GH_WORKFLOW_DIR"

if git diff --cached --quiet; then
    echo "No workflow changes to commit."
    exit 0
fi

git commit -m "Sync selected workflow templates"
git push

echo "Workflow templates synced and pushed to $ORG/$REPO."
