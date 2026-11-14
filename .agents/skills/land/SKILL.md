---
name: land
description: >-
  Land an existing pull request when asked to "land it": mark ready, enqueue,
  resolve blockers, wait for merge, and update the appropriate local checkout.
---

# Land

Treat "land it" as authorization to carry the identified PR through this workflow.

1. Confirm the repository, PR, target branch, local changes, and checkout topology. Use `git worktree list --porcelain` and Git directory/common-directory paths to distinguish an ordinary clone from a linked worktree. Ask only if the intended PR is ambiguous.
2. Check readiness, required CI, reviews, and mergeability. Mark the PR ready and enqueue using the repository's established mechanism; discover whether that means a label, native merge queue, or auto-merge.
3. Monitor until merged. Resolve relevant CI failures, conflicts, and actionable review findings within the agreed scope; run appropriate checks, commit with normal signing, and push fixes. Re-enqueue if needed. Preserve unrelated changes and existing authorization boundaries.
4. Observe the merged state and merge commit explicitly. Queue admission or enabled auto-merge is not completion.
5. After merge:
   - **Ordinary clone:** switch to the PR's target branch (usually `main`) and pull with `--ff-only` from its intended remote.
   - **Linked worktree:** leave its branch and files in place. Do not switch it to the target branch, pull the target branch there, remove it, or modify another checkout unless requested.
   - Respect branches checked out in other worktrees. Preserve dirty files and stashes; report any checkout or update blocked by them.
6. Report the PR link, merge result, and local branch/update status, including anything intentionally left in place.

Use bounded polling and provide progress updates during long waits. Investigate failures before retrying. Stop and explain blockers that require new decisions or authority; do not bypass required checks, force-push, dismiss reviews, or broaden the change just to merge. Do not delete branches or worktrees unless requested.
