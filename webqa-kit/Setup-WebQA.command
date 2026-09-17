#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
echo 'Setting up WebQA. This is only needed once.'
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m playwright install chromium
echo 'Setup complete. Open Start-WebQA.command to use WebQA.'
