#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Apply the Codex session's mise environment to Bash-compatible tool commands.

The hook rewrites commands rather than exporting variables in its own process.
Mise runs inside the tool's sandbox at execution time, keeping environment values
out of hook output and leaving the tool's requested working directory intact.
"""

import json
import shlex
import shutil
import sys
from pathlib import Path


def rewrite(event: dict) -> dict:
    """Prefix the original command using the session cwd supplied by Codex.

    Only the normalized command is replaced; Codex retains execution options
    such as the tool's working directory. Abort before the original command if
    mise fails, since executing without the project environment is misleading.
    """
    cwd = event["cwd"]
    command = event["tool_input"]["command"]
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise ValueError("The hook requires an absolute session cwd")
    if not isinstance(command, str):
        raise ValueError("The hook requires a string command")
    mise = shutil.which("mise")
    if mise is None:
        raise ValueError("mise must be installed and available on PATH")

    # A temporary shell variable preserves mise's exit status before evaluation.
    # Remove it before the original command so it cannot become application state.
    load = shlex.join([mise, "-C", cwd, "env", "--shell", "bash"])
    rewritten = (
        f'__codex_mise_env="$({load})" || exit $?\n'
        'eval "$__codex_mise_env" || exit $?\n'
        "unset __codex_mise_env\n"
        f"{command}"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": rewritten},
        }
    }


def main() -> int:
    """Read one Codex hook event and emit a rewrite or an explicit denial."""
    try:
        result = rewrite(json.load(sys.stdin))
    except (KeyError, TypeError, ValueError) as error:
        print(f"Cannot prepare the session mise environment: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
