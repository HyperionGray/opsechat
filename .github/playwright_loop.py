import requests
import os
import sys

# Configuration from environment variables (recommended for security)
# Set these as environment variables:
# export GITHUB_TOKEN="your_personal_access_token"
# export GITHUB_ORG="your-org"
# export GITHUB_REPO=".github"
# export WORKFLOW_FILENAME="copilot-org-playwright-loop.yml"

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
ORG = os.environ.get('GITHUB_ORG', 'your-org')
REPO = os.environ.get('GITHUB_REPO', '.github')
WORKFLOW_FILENAME = os.environ.get('WORKFLOW_FILENAME', 'copilot-org-playwright-loop.yml')

# API endpoint for workflow_dispatch
url = f'https://api.github.com/repos/{ORG}/{REPO}/actions/workflows/{WORKFLOW_FILENAME}/dispatches'

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json'
}

data = {
    "ref": "main"   # Branch to run workflow from. Use 'master' if needed.
    # If your workflow takes inputs, add them here in the "inputs" dict.
    # "inputs": {
    #     "param1": "value1",
    # }
}

if not GITHUB_TOKEN:
    print('Error: GITHUB_TOKEN environment variable is not set.')
    print('Please set it with: export GITHUB_TOKEN="your_personal_access_token"')
    sys.exit(1)

response = requests.post(url, headers=headers, json=data)

if response.status_code == 204:
    print('Workflow triggered successfully!')
else:
    print('Failed to trigger workflow')
    print('Status code:', response.status_code)
    print('Response:', response.text)
