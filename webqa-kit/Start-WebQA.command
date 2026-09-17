#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Run Setup-WebQA.command once before starting WebQA.'
  exit 1
fi
.venv/bin/python -m webqa ui
