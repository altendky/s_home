# Temporary Files

Use a temporary directory under `${TMPDIR:-/tmp}/agents/`. Create it on first need
using `mkdir -p "${TMPDIR:-/tmp}/agents" && mktemp -d "${TMPDIR:-/tmp}/agents/XXXXXXXXXX"`
and reuse the same path for the remainder of the session.
