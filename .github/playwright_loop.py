import requests
import os
import sys

# Replace these values!
# PLACEHOLDER - Replace with actual GitHub token
GITHUB_TOKEN = 'ghp_your_github_pat_here'     # Your GitHub personal access token with workflow access
ORG = 'your-org'
REPO = '.github'                              # Or any repo where your workflow lives
WORKFLOW_FILENAME = 'copilot-org-playwright-loop.yml'  # The workflow YAML file you want to run

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

response = requests.post(url, headers=headers, json=data, timeout=30)

if response.status_code == 204:
    print('Workflow triggered successfully!')
else:
    print('Failed to trigger workflow')
    print('Status code:', response.status_code)
    print('Response:', response.text)
