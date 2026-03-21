#!/bin/bash

# Archived one-off script for targeted pytest checks.
echo "Running the specific failing tests..."

cd /workspace

python -m pytest tests/test_runserver_helpers.py::test_check_older_than_detects_stale_entry -v
python -m pytest tests/test_runserver_helpers.py::test_check_older_than_keeps_recent_entry -v
python -m pytest tests/test_runserver_helpers.py::test_process_chat_wraps_long_messages -v
python -m pytest tests/test_runserver_helpers.py::test_process_chat_preserves_pgp_blocks -v

echo "Test run completed."
