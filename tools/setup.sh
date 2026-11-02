#!/bin/sh
set -eu
cd /workspace/eAcc-demo
python3 -m venv .runtime/venv
.runtime/venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.runtime/venv/bin/python -m py_compile server.py catalog.py integrations.py codef_adapter.py
