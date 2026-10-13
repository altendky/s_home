---
name: cleanup-agent-temp
description: Audit ownership and reclaim space in agent temporary directories, including legacy directories without breadcrumbs and partial removal of regenerable build caches. Use for agent temporary-file cleanup or attribution, not general filesystem cleanup.
---

# Agent temporary directory cleanup

Help the user identify who owns temporary material, whether it is still used,
and what can be removed within the requested scope. Use the current host's
runtime interfaces; agent names and session storage locations vary.

Read [ownership.md](references/ownership.md) when interpreting or writing
`owner.json`. The [JSON Schema](references/owner.schema.json) defines version 1.

## Establish scope and ownership

- Inspect the requested root, ordinarily `${TMPDIR:-/tmp}/agents`. Keep this
  audit's own files in its recorded session directory and exclude it from cleanup.
  Never mistake protected hidden directories or a symlink target for disposable
  temporary material. Do not follow symlinks or cross nested mounts during deletion.
- Inventory allocated sizes and the largest children before opening task content.
  Identify worktrees, recovery material, deliverables, caches and build outputs.
  Report the measurement time because other sessions can change the tree.
- Validate breadcrumbs structurally and check their lifecycle invariants. Missing,
  malformed, contradictory or newer-version metadata gives unknown ownership;
  preserve it and continue read-only discovery. Do not silently replace it.
- Resolve available session IDs against current runtime state. Distinguish a
  loaded session, a running turn, an active child job, and an owner that has
  released its claim. A shared agent daemon PID can host many sessions. Host and
  sandbox PIDs differ; neither a bare PID nor an absent open file proves liveness
  or abandonment. Record visibility gaps as unknown.
- Check current working directories, command path references, open descriptors
  and relevant container mounts for proposed deletions. If `/proc` is isolated,
  use an available host interface with the required execution permission; do not
  infer host state from the sandbox's process list.

For legacy directories, use narrow filename and metadata clues first. Search
authorized history for exact directory names only when attribution needs it;
capture session identifiers and relevant creation/use evidence rather than
copying conversation content. A directory's creator may differ from its current
user. Treat incidental listings as references, not adoption. Honor the global
session-access rules, including the OpenCode diagnostics skill when applicable.
Do not label a legacy directory `ready` merely because its creator was not found.

## Choose the appropriate cleanup

An audit request permits read-only work. When deletion is requested, carry out
clearly disposable cleanup within that authorization without asking again for
each directory. Present any uncertain or additional destruction separately.

**Partial space recovery:** choose specific regenerable paths whose deletion
does not discard source, unique outputs, or active work. A live owning session
does not prohibit all partial cleanup, but its active jobs and retained paths
still constrain the choice. Metadata cache labels are hints, not deletion grants.

- Rust `target/` or configured target directories can include saved executables
  and requested deliverables. Verify the actual directory and retained outputs
  before removing it; do not remove a source directory named `target` by name alone.
- Android/Gradle `intermediates`, `tmp`, `kotlin` and project `.gradle` directories
  are often regenerable. Preserve APKs/AABs, native libraries, requested reports
  and test evidence unless the user includes them in cleanup. SDK/NDK directories
  named `build` are installed tools, not project build caches.
- Python environments and download caches are candidates when their identity
  and recreation inputs are known. Check linked environments and installed tools
  before removing caches that may supply hard-linked or symlinked files.
- In repositories, verify candidate paths are ignored and contain no tracked
  files. Inspect for untracked source or special retention even when ignored.
  Avoid broad `git clean` and repository-wide cleanup commands.

Prefer older, inactive output when there is ample choice, but do not use a fixed
age threshold as proof of disposability. Respect current task requirements for
offline builds or retained binaries. Never terminate another session's jobs just
to reclaim space without authorization.

**Whole directories:** combine recorded releases and retention decisions with
current runtime and filesystem evidence. `ready` is a useful claim to verify,
not an unconditional deletion instruction. Missing release records or crashed
owners require an explicit cleanup decision based on current evidence and user
scope; never fabricate an owner's release to make a directory qualify.

For registered worktrees, inspect dirty files and commit reachability in the
owning repository. Preserve wanted work and remove worktrees with
`git worktree remove`; do not recursively delete their parent first. Review
patches, untracked-file archives and recovery copies before deleting them. A
clean worktree alone does not establish that its commits are disposable.

## Execute and verify

Prepare a concrete list of exact paths, their sizes, why they are disposable,
what will remain, and any unknown ownership. Keep a deletion record in this
audit's session directory. If approval is needed, finish this list before asking;
do not treat an audit or this skill's invocation as blanket deletion permission.

Recheck each selected path immediately before deletion for new activity,
retention, tracked/dirty content, symlink substitutions and mount boundaries.
Serialize metadata changes using the ownership protocol. Stop on an unexpected
change or failure and preserve the affected path; do not silently broaden the
cleanup or retry through another removal method.

After cleanup, verify selected paths are gone, protected worktrees and artifacts
remain, and ownership metadata still describes what is present. Partial cache
cleanup does not release any owners. Remove or update only the resource entries
for paths actually removed. Record who performed cleanup separately from who
created or adopted the material.

Report the paths/categories removed, measured free space, preserved material and
remaining blockers. Distinguish directory byte totals from filesystem space
actually reclaimed: hard links, sparse files, open deleted files and concurrent
writes can change the result. Leave a concise audit record and an accurate
retention breadcrumb if the user needs to review it later.
