# Temporary directory ownership record, version 1

`owner.json` lives at the root of the session temporary directory. The
[JSON Schema](owner.schema.json) describes its shape. This record supports
attribution and cleanup decisions; it is neither a process lease nor authority
to delete files. Do not store secret values or conversation transcripts.

Enable date-time format checks when validating with a JSON Schema library.
Check claim-ID uniqueness and timestamp ordering separately: creation/join precede last use or release,
and `updated_at` is at least as recent as the recorded changes. Schema validation
does not establish path containment, live ownership, or actual disposability.

## Fields

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`. Preserve unfamiliar versions for review. |
| `created_at`, `updated_at` | UTC RFC 3339 timestamps ending in `Z`. |
| `purpose` | Short task description. |
| `owners` | Append-only identity history; update each owner's activity/release fields in place. |
| `cleanup_state` | Aggregate intent: `in-use`, `retained`, or `ready`. |
| `retained` | Relative paths, reasons and conditions permitting removal. |
| `worktrees` | Relative worktree roots and absolute paths to their owning repositories. |
| `jobs` | Background processes/containers using this directory, with runtime-qualified identities. |
| `generated` | Optional relative paths, resource kinds and recreation instructions. |

Use literal relative paths for resources; `.` denotes the whole directory. Do not
use globs, absolute paths or `..` components in resource paths. Validate containment
against the actual root before acting, including symlinks and mount points. An
owning repository path is intentionally absolute and is not a deletion target.

Each owner records `claim_id`, `tool`, `session_id`, `agent_id`, `cwd`, `joined_at`,
`last_used_at`, and `released_at`. Use `null` for identifiers that the runtime
does not expose, and for `released_at` until that owner releases its claim. The
creator is the first entry. Include an exposed subagent identity so multiple
agents sharing a session are distinguishable. An unknown identity is a real
uncertainty, not grounds to merge two owners or invent a session identifier.

Claim ownership when creating or modifying task material, or adopting it for
work you may resume. Read-only audits and incidental directory listings do not
adopt the inspected directories. Record collaborators who actually share the
workspace; do not enroll every observer as an unreleased owner.

Generate a UUID `claim_id` when adding an owner entry and keep it in the current
session context. It identifies this metadata claim, not an agent runtime session.
Use it when touching or releasing your claim, especially when session/subagent
identifiers are unavailable. Claim IDs must be unique within the record. If you
cannot establish which existing claim is yours on resumption, add a new claim
and preserve the uncertain old one rather than releasing it.

An optional `runtime` contains `host`, `namespace`, `pid` and `started_at`.
Record these only when known; the host/namespace and process start time are needed
to check a PID without confusing reuse or sandbox identity. Prefer session IDs
for attribution. `runtime` is a hint; it is not required to create a breadcrumb.

A job's `identity` is a runtime-qualified reference, such as a tool execution
session ID, container ID, or host/PID/start-time tuple. `kind` and `description`
explain what uses the directory. An unknown identity can be `null`; unknown job
liveness keeps the directory in use. Remove a job entry only after it ends or is
confirmed to no longer use this material.

`generated` entries are optional inventory aids. Their presence does not imply
that another agent has permission to delete them. `retained` takes precedence
over overlapping generated paths; retention of `.` covers everything. Record
only what is useful to locate a resource or make a cleanup decision.

## Lifecycle and concurrent updates

1. Immediately after `mktemp`, create the record with the current owner, empty
   resource lists, and `cleanup_state: "in-use"`, before creating task files.
2. Touch that owner's `last_used_at` on resumption, meaningful changes and before
   yielding; update `updated_at` on every metadata change. No heartbeat is required.
3. A new session or subagent that uses the directory appends its owner entry.
   Resuming your known claim updates that entry and clears its release;
   keep the original `joined_at`. Never erase the creator or previous users.
4. Register worktrees/jobs before using them, and record retained files as soon
   as they become meaningful. After removal, update only those resource entries.
5. Release only your own claim when you no longer expect to use this material.
   Yielding for a reply or awaiting a build is not a release. A missing/dead owner
   does not automatically release its claim, and a cleanup agent must not forge
   that release. Explicitly authorized cleanup of abandoned material is a separate
   decision recorded in the cleanup audit.
6. Keep `in-use` while any owner is unreleased or any job still uses the directory.
   Once all owners release and jobs are gone, use `retained` if anything must
   remain, listing its reason and release condition. A worktree awaiting review
   is retained material; record its path in both lists.
7. Use `ready` only after all owners release, all jobs end, registered worktrees
   are removed through Git, and retention is resolved. Remaining files must be
   disposable. The cleanup skill still verifies actual contents and runtime use.

For every write, acquire an exclusive file lock on the stable `owner.lock` file,
read the latest record under that lock, merge only your intended changes, write
a temporary sibling file, and atomically replace `owner.json`. Hold the lock
through replacement. Do not replace the lock file or overwrite metadata from a
stale in-memory copy. This lock serializes edits; its existence is not liveness
evidence. Coordinate with other known writers before changing a shared record
when compatible locking is unavailable. Bootstrap the initial record under the
same lock and do not overwrite an existing record.

After acquiring the lock, check that the directory still exists and the opened
lock is still the file at `owner.lock`; fail if either identity changed. Cleanup
holds the same lock from its final reread through whole-directory removal. A
waiting writer must not recreate a removed directory or continue on an unlinked
lock. For partial cleanup, hold the lock through the affected metadata update
and recheck actual resource use; metadata locking does not stop build processes.

Missing, malformed or contradictory records are legacy/unknown, not `ready`.
Keep their original bytes. If a migration is needed, preserve the old record
and explicitly record the limits of inferred identity rather than claiming
an unverified owner released it. Version 1 metadata is small enough to write
with available tools; no daemon or periodic process is required.

## Minimal initial example

```json
{
  "schema_version": 1,
  "created_at": "2026-10-13T15:00:00Z",
  "updated_at": "2026-10-13T15:00:00Z",
  "purpose": "Investigate a failing build",
  "owners": [
    {
      "claim_id": "11111111-2222-4333-8444-555555555555",
      "tool": "codex",
      "session_id": null,
      "agent_id": null,
      "cwd": "/home/user/repos/project",
      "joined_at": "2026-10-13T15:00:00Z",
      "last_used_at": "2026-10-13T15:00:00Z",
      "released_at": null
    }
  ],
  "cleanup_state": "in-use",
  "retained": [],
  "worktrees": [],
  "jobs": [],
  "generated": []
}
```

For a retained report, an entry could be
`{"path":"results.txt","reason":"User review","release_when":"User has reviewed or saved the report"}`.
Retention conditions describe a decision to verify; they are not automatic expiry
or commands to execute.
For a worktree, use `{"path":"review-tree","repository":"/home/user/repos/project"}`.
