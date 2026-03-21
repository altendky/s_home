---
description: Catch up constituent branches and recreate a combined integration branch
---

# Recombine

**Arguments:** $ARGUMENTS

## Pre-flight check

This command executes git operations that modify local branches. Before
proceeding, verify that your current mode permits running bash commands and
making changes. If your system instructions indicate you are in a read-only
or plan mode, stop immediately and ask the user to switch to the build agent
(Tab key) and re-run the command. Do not proceed to Phase 1 until you can
confirm you are able to take action.

Recreate a combined integration branch by catching up all its constituent
branches to the latest base branch, dropping any that have been fully merged
upstream, and rebuilding the combined branch from scratch.

## Principles

- Never force push. All pushes use regular `git push`.
- Only push branches that already have a configured upstream tracking remote.
  Skip any that don't.
- The only destructive operation is deleting and recreating the local combined
  branch itself.
- Do not modify branches beyond merging the base branch into them.
- When merge conflicts occur, present them to the user and let them decide how
  to proceed — do not silently abort or auto-resolve without approval.
- This command focuses narrowly on incorporating upstream changes and
  rebuilding the combined branch. It does not perform general repository
  cleanup (e.g., pruning stale remote-tracking references or deleting
  old branches beyond those identified as fully merged).

## Phase 1: Identify context

### 1.1 Parse arguments

Optional positional arguments: `[combined-branch] [base-branch]`

- **combined-branch**: Name of the combined integration branch. Default:
  `combined`.
- **base-branch**: Name of the base branch to catch up to. Default:
  auto-detect.

### 1.2 Determine the base branch

If not specified, detect the default branch:

1. Check `git symbolic-ref refs/remotes/upstream/HEAD` or
   `git symbolic-ref refs/remotes/origin/HEAD`.
2. Fall back to checking which of `dev`, `main`, `master` exists as a local
   branch tracking a remote.
3. If ambiguous, ask the user.

### 1.3 Fetch all remotes

```
git fetch --all
```

### 1.4 Update local base branch

Fast-forward the local base branch to its upstream:

```
git checkout <base-branch>
git merge --ff-only <upstream>/<base-branch>
```

If this fails (local base has diverged), stop and ask the user.

### 1.5 Identify constituent branches

Find all local branches that are constituent parts of the combined branch.
A branch qualifies if **both**:

- Its tip is an ancestor of the combined branch
  (`git merge-base --is-ancestor <branch> <combined>`).
- It has non-merge commits not present in the base branch
  (`git log --oneline <base>..<branch> --no-merges` is non-empty).

Skip the base branch and the combined branch themselves.

Present the discovered list to the user for confirmation. Allow them to add or
remove branches before proceeding.

## Phase 2: Classify constituent branches

For each constituent branch, determine if its unique changes are now in the
base branch (i.e., its PR was merged upstream).

1. Check `git log --oneline <base>..<branch> --no-merges` — if empty, the
   branch is fully merged. Mark for **dropping**.
2. If commits exist, check if the code diff is empty:
   `git diff <base>...<branch>`. If empty (squash-merged upstream), mark for
   **dropping**.
3. Otherwise, mark for **keeping**.

For each branch, also check its upstream tracking status:

1. `git for-each-ref --format='%(upstream:short)' refs/heads/<branch>` to get
   the configured upstream (if any).
2. If an upstream is configured, extract the remote and branch name and run
   `git ls-remote --heads <remote> <branch>` to verify it still exists on the
   remote.

Present the classification, including the upstream status for each branch:

- **Dropping** (merged upstream): list branch names with upstream status
  (e.g., "upstream: gone" or "upstream: origin/my-branch").
- **Keeping** (still has unmerged work): list branch names with commit counts,
  upstream status, and any associated PRs
  (`gh pr list --head <branch> --state all --json number,title,state`).

Ask the user to confirm before proceeding.

## Phase 3: Catch up remaining branches

For each branch marked for keeping:

1. `git checkout <branch>`
2. `git merge <base-branch> --no-edit`
3. If the merge is clean, continue.
4. **If conflicts occur:**
   - List the conflicted files and show a summary of the conflicts.
   - Present options to the user:
     - **Resolve**: attempt to resolve the conflicts (use analysis and editing
       to fix them, then ask the user to verify).
     - **Skip**: abort this merge (`git merge --abort`) and remove this branch
       from the set of kept branches. It will not be included in the combined
       branch.
     - **Abort**: abort the entire recombine operation, restoring the original
       combined branch first.

Track which branches were successfully updated.

## Phase 4: Recreate the combined branch

1. `git checkout <base-branch>`
2. `git branch -D <combined-branch>` — delete the old local combined branch.
3. `git checkout -b <combined-branch>` — create fresh from base.
4. For each kept branch (in the order they were listed in Phase 1):
   `git merge <branch> --no-edit`
5. **If conflicts occur** during any merge into combined:
   - Present the conflicted files and a summary of the conflicts.
   - Present options:
     - **Resolve**: attempt to resolve the conflicts, then ask the user to
       verify.
     - **Skip**: abort this merge (`git merge --abort`) and exclude this
       branch from combined. Continue with the remaining branches.
     - **Abort**: stop here. The combined branch is in a partially-built
       state; note which branches have been merged and which haven't.

## Phase 5: Push updated branches

For each branch that was updated (had new commits merged) in Phase 3:

1. Check if the branch has a configured upstream:
   `git for-each-ref --format='%(upstream:short)' refs/heads/<branch>`
2. If it has an upstream, push with `git push`.
3. If it does not, skip and note that it was not pushed.

**Never push the combined branch** unless it already has a configured upstream
tracking remote.

**Never force push any branch.**

If the push fails due to pre-existing issues (e.g., a pre-push hook that fails
on the base branch itself), inform the user and offer to retry with
`--no-verify`. Only use `--no-verify` with explicit user approval.

## Phase 6: Report and cleanup

Present a summary:

- Base branch updated to: `<commit>`
- Branches dropped (merged upstream): list with upstream status
- Branches kept and caught up: list with push status
- Branches skipped due to conflicts: list (if any)
- Combined branch recreated with: list of merged branches
- Any issues encountered

If any branches were dropped (identified as fully merged upstream), offer to
delete them locally:

1. List the branches that would be deleted.
2. Ask the user to confirm before proceeding.
3. For each confirmed branch: `git branch -D <branch>`.
4. Do not delete any branches the user declines.
