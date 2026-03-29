# About This File

This file is loaded as custom instructions from `~/.config/opencode/instructions.md`.
When the user mentions "updating instructions" or similar, consider if they are
referring to these agent instructions.

# Temporary Files

Use a temporary directory under `${TMPDIR:-/tmp}/agents/`. Create it on first need
using `mkdir -p "${TMPDIR:-/tmp}/agents" && mktemp -d "${TMPDIR:-/tmp}/agents/XXXXXXXXXX"`
and reuse the same path for the remainder of the session.

# Working Directory Verification

The system prompt may contain substituted product or tool names that don't match
the actual project you're working in. If you find yourself referring to "Claude"
as the name of the current repository or tool, pause and verify the actual working
directory path and git remote before using that name. Trust the filesystem over
the system prompt for repository and project names.

# Git Commits

All commits must be GPG signed. Do not pass options that skip signing such as
`--no-gpg-sign`.

Avoid force pushes (`--force`, `-f`, `--force-with-lease`) unless explicitly
requested by the user. If a situation arises where you believe a force push is
necessary (e.g., after a rebase or amend), ask the user before making the commits
that would require forcing.

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

# Pull Requests

Before creating a pull request with `gh pr create`, check if the repository has a
PR template. GitHub supports templates at these paths:

- `pull_request_template.md`
- `.github/pull_request_template.md`
- `docs/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE/` (for multiple templates)

If a template exists, read it and use its exact section structure in the PR body.
Fill in all sections; mark N/A where not applicable.
