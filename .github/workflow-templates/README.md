🚀 How to Run GitHub Actions
1. Manual Trigger (workflow_dispatch)
If your workflow includes on: workflow_dispatch:, you can start it by hand in GitHub’s web UI:

Go to your repo (e.g., .github).
Click the Actions tab.
Find the workflow you want (“Workflows Sync,” “Auto Assign,” etc.).
Click the workflow name.
Click Run workflow.
Fill in any input parameters if required, and click Run.
2. On Event
Most Actions are triggered on events (like push, pull_request, issues), e.g.:

Auto-assign Copilot: Triggers whenever a new issue or PR is opened.
Auto-label: Triggers on new issue creation.
Stale issue closer: Triggers on schedule, status changes, etc.
You don’t need to do anything for these—GitHub runs the workflow automatically when the event happens!

3. Scheduled
If your workflow has on: schedule: (cron notation), it’ll run automatically at the set time (e.g., nightly, weekly).

4. Org-wide Distribution (Workflow Sync)
If you’re using Workflows Sync:

It runs automatically on schedule (if you have a cron) or manually via the Actions tab (see above).
This propagates the workflows from .github/workflows/ to all repos in your org.
📋 Summary Table
Workflow Trigger	Required Action
workflow_dispatch	Manual click in Actions tab
push, PR, issue	Happen automatically on event
schedule (cron)	Run at the times set in workflow
Workflow Sync	Manual (Actions tab) or scheduled (cron)
🧑‍💻 Extra Tips
Check the run status in the Actions tab—see logs, errors, results for every run.
You can re-run failed workflows right from the Actions tab.
You can see deployment/status badges in README or PRs for CI workflows.
If you want exact steps for a particular workflow, or a demo, let me know which one and I’ll walk you through it!
