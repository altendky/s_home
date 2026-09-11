---
name: opencode-diagnostics
description: "Diagnose OpenCode v1/v2 runtime logs and session storage, retrieval, import, or export problems, and inspect specifically requested past sessions or exports. Use for OpenCode diagnostics and authorized session inspection, not ordinary coding tasks performed in OpenCode."
---

# OpenCode Diagnostics

Follow the [global session-access rules](../../AGENTS.md#opencode-diagnostics-and-session-access),
including their exceptions. Scope session listing, exports, and database queries
to the requested investigation; do not reuse conversation content for unrelated
discovery.

## Identify The Runtime

Resolve the executable and inspect its version and relevant command help before
choosing an interface. The command named `opencode` may run v2. Below, `opencode`
denotes v1 and `opencode2` denotes v2; substitute the actual executable.

Paths below assume Linux XDG defaults. The data directory is
`${XDG_DATA_HOME:-$HOME/.local/share}/opencode`. Resolve the database path rather
than guessing from the executable name or channel. If installed help and online
documentation disagree, inspect the source matching the installed build.

## OpenCode V1

### Runtime Logs

When debugging OpenCode itself, look first in the data directory's `log/` folder.
V1 writes timestamped files such as `2026-03-20T234041.log` and retains roughly
ten recent files. Lines follow this format:

    LEVEL YYYY-MM-DDTHH:MM:SS +<delta>ms key=value ... message

`--print-logs` sends logs to stderr; `--log-level DEBUG|INFO|WARN|ERROR` controls
verbosity.

### Sessions And Storage

- `opencode session list --format json --max-count <N>` lists sessions.
- `opencode export <sessionID>` writes the session as JSON to stdout. Prefer an
  explicit ID over opening a picker of unrelated sessions.
- `opencode import <file-or-share-url>` imports a session. This changes stored
  data and belongs to requested import or recovery work.
- `opencode db path` prints the database path. Stable builds normally use
  `opencode.db`; channel builds can use `opencode-<channel>.db`, including
  `opencode-dev.db` for v1 dev builds. `OPENCODE_DB` overrides the path; a relative
  override resolves under the data directory.
- `opencode db "<SQL>"` executes supplied SQL with TSV output by default; it does
  not enforce read-only access. Bare `opencode db` opens an ordinary SQLite shell.
  For inspection, prefer `sqlite3 -readonly "<resolved-db-path>"` and read-only
  queries.

The legacy schema contains `session`, `message`, and `part` tables, with IDs
prefixed `ses_`, `msg_`, and `prt_`. Message and part JSON is stored in `data`
columns. Inspect the actual schema before writing queries.

In the v1 TUI, the default `<leader>x` binding opens Markdown session export;
check configured bindings if it behaves differently.

## OpenCode V2

### Runtime Logs

Installed builds write `log/opencode.log` under the data directory; local source
builds use `log/opencode-local.log`. Lines include `timestamp`, `level`, `run`,
and `role` fields. Filter for the relevant run and role, particularly
`role=server` when investigating server behavior. Do not apply v1's timestamped
filename or retention assumptions.

V2 supports `OPENCODE_LOG_LEVEL=DEBUG|INFO|WARN|ERROR`. `--print-logs` adds stderr
output while retaining file logs. Background server logs remain in the file;
server stderr requires running with `--standalone`. Check help before using v1's
`--log-level` flag.

### Sessions And Storage

- `opencode2 service status` checks service state without starting it.
- `opencode2 session list --format json --max-count <N>` lists recent top-level
  sessions for the current project.
- `opencode2 export <sessionID>` writes transfer JSON; `--sanitize` is available.
- `opencode2 import <file-or-url>` imports transfer JSON and changes stored data.
  Check format compatibility before treating a v1 share URL as a valid input.
- Session listing, export, and import may start a background server. Account for
  that when investigating startup or storage behavior; they are not direct
  filesystem reads.
- `opencode2 debug paths` prints resolved paths. Some documentation advertises
  `debug paths db` and `debug paths log` selectors that local builds may lack;
  check installed help before using a selector.

V2 channels including `latest`, `dev`, `beta`, `next`, and `prod` currently share
`opencode.db`; other channels can use suffixed names. `OPENCODE_DB` overrides the
path, with relative values resolved under the data directory. Use the resolved
path instead of assuming v1's dev database naming.

V2 does not provide the legacy `db` command in the inspected interface. When
necessary, use `sqlite3 -readonly "<resolved-db-path>"` for scoped inspection.
V2 uses a different schema, including `session_v2` and `session_message`; inspect
it before querying rather than applying the v1 table or JSON-column assumptions.

The default v2 `<leader>x` binding opens export options for Markdown or JSON.

## Interface References

Check the documentation for the relevant major version:

- [V1 CLI](https://opencode.ai/docs/cli) and
  [V1 troubleshooting](https://opencode.ai/docs/troubleshooting#logs).
- [V2 CLI](https://opencode.ai/v2/docs/cli) and
  [V2 troubleshooting](https://opencode.ai/v2/docs/troubleshooting).
