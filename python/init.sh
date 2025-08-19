#/usr/bin/env bash
uv venv --allow-existing
uv pip install -r requirements.txt
source .venv/bin/activate