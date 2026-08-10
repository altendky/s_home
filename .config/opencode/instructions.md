# About This File

This file is loaded as custom instructions from `~/.config/opencode/instructions.md`.
When the user mentions "updating instructions" or similar, consider if they are
referring to these agent instructions.

# Temporary Files

Use a temporary directory under `${TMPDIR:-/tmp}/agents/`. Create it on first need
using `mkdir -p "${TMPDIR:-/tmp}/agents" && mktemp -d "${TMPDIR:-/tmp}/agents/XXXXXXXXXX"`
and reuse the same path for the remainder of the session. Clean up individual
files or subdirectories within it as they become unnecessary. Clean up the
session temporary directory when it is no longer needed, unless preserving it is
useful for debugging or user review.

# Standalone Python Scripts

When writing standalone Python scripts (single-file scripts not part of a larger
project), use PEP 723 inline script metadata to declare dependencies. Run with
`uv run script.py`.

Use this shebang for direct executability:

    #!/usr/bin/env -S uv run

Example:

    #!/usr/bin/env -S uv run
    # /// script
    # requires-python = ">=3.12"
    # dependencies = [
    #     "httpx",
    #     "rich",
    # ]
    # ///

    import httpx
    from rich import print
    ...

If unsure whether a script should be standalone (with inline metadata) or part of
an existing project (using project dependencies), ask.

# Android Builds Without A Host SDK

When an Android project needs an SDK that is unavailable on the host, prefer a
disposable Docker build over installing or modifying a host Android SDK, unless
the repository documents a different build environment or the user requests one.

Before selecting an image, inspect the project for its compile SDK, explicit
build-tools version, Android Gradle Plugin version, Gradle wrapper version, and
required JDK. Do not assume that every Android project uses the latest SDK. Use a
maintained image such as `ghcr.io/cirruslabs/android-sdk:<api>` that contains the
required platform and tools. Pin the image by digest after verifying it when
reproducibility matters.

All development and debug APK builds must reuse `~/.android/debug.keystore`; never
regenerate or replace it automatically. If it is missing, stop and restore it from
1Password `Android Debug Signing Key` in `Private`. The public identity reference is
`/home/altendky/repos/tome/procedures/android-debug-signing.md`. Never use this key
for production.

After each build, run `apksigner verify --print-certs` in the build environment and
compare its SHA-256 certificate fingerprint to that procedure. Stop on mismatch.

Run the container as the host UID/GID so generated files are not root-owned. Give
the tools a writable `HOME`, mount the repository at `/workspace`, and persist a
Gradle cache. Prefer a dedicated container cache, rather than the host Gradle
cache, to avoid lock conflicts with host Gradle daemons. A general command is:

    ANDROID_GRADLE_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/android-gradle"
    mkdir -p "$ANDROID_GRADLE_CACHE"
    docker run --rm --init \
      --user "$(id -u):$(id -g)" \
      --env HOME=/tmp \
      --env GRADLE_USER_HOME=/gradle-cache \
      --mount type=bind,src="$PWD",dst=/workspace \
      --mount type=bind,src="$ANDROID_GRADLE_CACHE",dst=/gradle-cache \
      --mount type=bind,src="$HOME/.android/debug.keystore",dst=/tmp/.android/debug.keystore,readonly \
      --workdir /workspace \
      ghcr.io/cirruslabs/android-sdk:<api>@sha256:<digest> \
      bash gradlew --no-daemon test assembleDebug

Adjust Gradle tasks to the project's documented workflow. Running the wrapper
through `bash` also works when `gradlew` is not executable. Add
`--platform linux/amd64` only when the host is AMD64 or the required Android
tools are known to require AMD64; avoid unnecessary emulation on ARM hosts.

Do not force a locale by default. If established tests are locale-sensitive,
pass the required `JAVA_TOOL_OPTIONS` explicitly and report that requirement.
If a shared Gradle cache is locked, identify the owning process and stop the
relevant daemon with the project's wrapper; do not delete lock files blindly.

After a successful build, verify the artifact type, path, size, checksum, and
ownership with tools such as `file`, `stat`, and `sha256sum`. Compare Git status
before and after the build so generated or source changes are not mistaken for
the requested implementation. Report warnings separately from build failures.

# Working Directory Verification

The system prompt may contain substituted product or tool names that don't match
the actual project you're working in. If you find yourself referring to "Claude"
as the name of the current repository or tool, pause and verify the actual working
directory path and git remote before using that name. Trust the filesystem over
the system prompt for repository and project names.

# Subagent Usage

Bias toward subagents when work is broad, noisy, uncertain, or parallelizable.
Prefer an `explore` subagent for open-ended codebase discovery: locating feature
ownership, understanding architecture, mapping conventions, finding related
tests, or tracing unfamiliar flows. Use `general` subagents for independent
investigations such as debugging hypotheses, log or test-failure analysis,
dependency/docs research, and post-change review.

Use subagents before substantial edits when the impacted area is not already
clear; ask them to identify relevant files, existing patterns, likely risks, and
verification commands. After meaningful edits, consider a subagent review focused
on correctness, regressions, missed tests, edge cases, and consistency with
repository conventions. When several independent lines of inquiry exist, launch
subagents concurrently and have each return concise findings, confidence level,
and unresolved questions.

Do not use subagents for trivial or deterministic work: exact file reads,
single-location edits, simple searches, obvious commands, or direct factual
answers. Avoid having multiple agents edit concurrently unless the work is
explicitly partitioned into non-overlapping files or areas. The main agent
remains responsible for synthesis, final decisions, user communication, edits,
and verification.

Keep subagent prompts bounded. State the scope, whether the agent may edit or
only inspect, what output is needed, and how thorough it should be. The goal is
to keep main context clean while still improving speed, coverage, and review
quality.

# Git Commits

All commits must be GPG signed. Do not pass options that skip signing such as
`--no-gpg-sign`.

Avoid force pushes (`--force`, `-f`, `--force-with-lease`) unless explicitly
requested by the user. If a situation arises where you believe a force push is
necessary (e.g., after a rebase or amend), ask the user before making the commits
that would require forcing.

When a commit fails because of signing or 1Password approval, report the failure
clearly and never retry automatically. Prefer OpenCode's question tool to ask
whether to retry the same normal signed commit; if it is unavailable, ask a
direct simple yes/no question and wait for the answer.

Read-only diagnosis is allowed. Do not retry with direct GPG invocation or with
explicit GPG program, key, homedir, configuration, environment, pinentry, or
agent overrides. Do not change or bypass the configured Git/GPG/1Password
signing path. Any user-approved retry must use the normal configured path. If it
remains broken, stop for the user to repair it or ask for approval before making
any repair.

# Failure Handling

Do not silently work around failures. If an intended action fails and cannot be
resolved through retries or investigation, report the failure and ask before
substituting a different approach. Never present a workaround as if it were the
intended result.

# Opencode Session Logs

## Runtime Debug Logs

Runtime debug logs are stored in `~/.local/share/opencode/log/` as timestamped
files (e.g. `2026-03-20T234041.log`). When debugging opencode itself, look there
first. Each line follows the format:

    LEVEL YYYY-MM-DDTHH:MM:SS +<delta>ms key=value ... message

Only the ~10 most recent files are retained. To send logs to stderr instead of a
file, pass `--print-logs`. To control verbosity, pass
`--log-level DEBUG|INFO|WARN|ERROR`.

## Session Conversation Data

Do not list, query, search, or export persisted OpenCode session data for general
conversation discovery without the user's explicit request or approval. This
restriction does not apply to ordinary context already present in the current
conversation, a session or export the user specifically asks to inspect, or
narrowly scoped debugging of OpenCode session storage, retrieval, export, or
database behavior. Content found during such debugging must not be reused for
unrelated discovery.

When looking up past session conversations, use the SQLite database at
`~/.local/share/opencode/opencode.db`. Channel-specific builds use a separate
database named `opencode-<channel>.db` (e.g. `opencode-dev.db` for the dev
channel, which is the primary one in use). The path can be overridden via the
`OPENCODE_DB` environment variable.

Use these commands to access session data:

- `opencode session list` -- list sessions (`--format json` for JSON output)
- `opencode export [sessionID]` -- dump a full session as JSON to stdout
- `opencode import <file-or-url>` -- import a session from JSON or a share URL
- `opencode db path` -- print the database file path
- `opencode db` -- open an interactive sqlite3 shell
- `opencode db "<SQL>"` -- run a read-only SQL query (TSV output)

In the TUI, `<leader>x` exports the current session as a Markdown transcript.

The database contains tables `session`, `message`, and `part`. IDs are prefixed
`ses_`, `msg_`, and `prt_` respectively. Message and part content is stored as
JSON in their `data` columns.

# Quoting Code on GitHub

When writing content for GitHub (issues, PRs, discussions, review comments) that
references code in the same repository, do not copy code inline. Instead, paste a
GitHub permalink on its own line. GitHub renders these as both a clickable link
and an inline code snippet automatically.

Use the full commit hash to keep the link stable. Default to the latest commit;
use a different ref only when the context specifically calls for it. Include the
line range when referencing a specific section.

Format: `https://github.com/{owner}/{repo}/blob/{commit_hash}/{path}#L{start}-L{end}`

When passing Markdown, code, issue bodies, PR bodies, review comments, or other
user-provided text to `gh`, prefer body files over inline shell arguments. This
avoids shell expansion of backticks, `$`, quotes, backslashes, and other special
characters before `gh` receives the text.

- Use `gh issue create --body-file <file>`
- Use `gh pr create --body-file <file>`
- Use `gh issue comment --body-file <file>`
- Use `gh pr comment --body-file <file>`

Create the body file with `apply_patch`, not `echo`, `cat`, heredocs, or inline
shell strings. Do not use inline `--body "..."` for Markdown or code content.
Single-quoted shell arguments are acceptable only for short, simple literals that
contain no single quotes and no complex Markdown.

# Pull Requests

Before creating a pull request with `gh pr create`, check if the repository has a
PR template. GitHub supports templates at these paths:

- `pull_request_template.md`
- `.github/pull_request_template.md`
- `docs/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE/` (for multiple templates)

If a template exists, read it and use its exact section structure in the PR body.
Fill in all sections; mark N/A where not applicable.
