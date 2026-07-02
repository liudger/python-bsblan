#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"

should_run="$(HOOK_PAYLOAD="$payload" python3 - <<'PY'
import json
import os

edit_tools = {
    "edit",
    "write",
    "multi_edit",
    "multiedit",
    "apply_patch",
    "create_file",
    "insert_edit_into_file",
    "replace_string_in_file",
    "multi_replace_string_in_file",
    "edit_notebook_file",
    "create_new_jupyter_notebook",
    "mcp_github_create_or_update_file",
    "mcp_io_github_git_create_or_update_file",
}

# File extensions that require running the Python validation suite.
code_suffixes = (".py", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json")

raw = os.environ.get("HOOK_PAYLOAD", "").strip()
if not raw:
    print("skip")
    raise SystemExit(0)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("skip")
    raise SystemExit(0)

tool_name = str(data.get("tool_name") or data.get("toolName") or "").lower()
if tool_name not in edit_tools:
    print("skip")
    raise SystemExit(0)


def paths(value):
    """Yield path-like strings from tool input."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"filePath", "file_path", "path", "notebookPath"} and isinstance(
                item, str
            ):
                yield item
            else:
                yield from paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from paths(item)


tool_input = data.get("tool_input") or data.get("toolInput") or {}
edited = list(paths(tool_input))

# Only run the heavy validation when code/config files were touched.
# Docs, markdown, and memory edits do not need pytest + prek.
if edited and not any(p.lower().endswith(code_suffixes) for p in edited):
    print("skip")
    raise SystemExit(0)

print("run")
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
if ! SKIP=no-commit-to-branch uv run prek run --all-files; then
    echo "[hook] Prek failed"
    exit 2
fi

echo "[hook] Validation passed"
