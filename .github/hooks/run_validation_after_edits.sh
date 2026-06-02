#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"

should_run="$(HOOK_PAYLOAD="$payload" python3 - <<'PY'
import json
import os
import sys

edit_tool_tokens = {
    "edit",
    "write",
    "multi_edit",
    "multiedit",
    "apply_patch",
    "create_file",
    "edit_notebook_file",
    "create_new_jupyter_notebook",
    "mcp_github_create_or_update_file",
    "mcp_io_github_git_create_or_update_file",
}

def walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)
    elif isinstance(value, str):
        yield value

raw = os.environ.get("HOOK_PAYLOAD", "").strip()
if not raw:
    print("skip")
    raise SystemExit(0)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("skip")
    raise SystemExit(0)

haystack = "\n".join(s.lower() for s in walk(data))
if any(token in haystack for token in edit_tool_tokens):
    print("run")
else:
    print("skip")
PY
)"

if [[ "$should_run" != "run" ]]; then
    exit 0
fi

echo "[hook] File edit detected. Running validation commands..."

echo "[hook] Running tests"
if ! uv run pytest --no-cov; then
    echo "[hook] Tests failed"
    exit 2
fi

echo "[hook] Running prek"
if ! uv run prek run --all-files; then
    echo "[hook] Prek failed"
    exit 2
fi

echo "[hook] Validation passed"
