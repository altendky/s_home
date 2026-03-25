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

# Failure Handling

Do not silently work around failures. If an intended action fails and cannot be
resolved through retries or investigation, report the failure and ask before
substituting a different approach. Never present a workaround as if it were the
intended result.
