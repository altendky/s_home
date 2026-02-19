---
description: Merge a source branch into the current branch with deep analysis, parallel conflict resolution, and full verification
---

# Merge Branch

**Source branch:** $1

Merge the specified source branch into the current branch. This command is repo-agnostic and must be run from inside a Git repository.

## Principles

- Use the `task` tool aggressively to parallelize analysis work across files and branches.
- Think carefully and reason step-by-step for complex or ambiguous decisions that benefit from deeper consideration.
- Never assume project tooling. Discover check/test commands and confirm with the user.
- Present plans before making changes that affect code content. Require explicit approval at gates.
- Even clean merges get full analysis and verification.
- Be explicit about any code that will be lost or cannot be trivially preserved.

If $1 is not provided, ask the user to supply a branch name.

## Phase 1: Pre-checks

1. **Verify Git repo**: `git rev-parse --show-toplevel`. Stop with a clear message if not in a repo.

2. **Resolve refs**:
   - Current branch: `git rev-parse --abbrev-ref HEAD`
   - Source branch: verify $1 exists as a local branch, remote-tracking branch, or valid ref. If ambiguous or missing, ask the user to clarify.

3. **Check for in-progress operations**:
   - Check for ongoing merge (`git rev-parse -q --verify MERGE_HEAD`), rebase (`.git/rebase-apply`, `.git/rebase-merge`), cherry-pick (`.git/CHERRY_PICK_HEAD`), or revert (`.git/REVERT_HEAD`).
   - If any found: ask the user whether to abort and restart, or bail out.

4. **Verify clean working tree**:
   - `git status --porcelain`
   - If not clean: ask the user to stash, commit, or stop.

5. **Fetch and verify upstream freshness**:
   - `git fetch --all --prune --tags`
   - For the current branch: check if it has an upstream and whether it is behind. If behind, ask the user to fast-forward first.
   - For the source branch: check if it has an upstream and whether it is behind. If behind, offer to merge the upstream ref instead, update the local branch, or stop.

6. **Report**: state the current branch, the resolved source ref, and proceed.

## Phase 2: Branch topology and initial research

Goal: build a thorough understanding of both branches before merging.

### Topology

- **Merge base**: `git merge-base HEAD <source>`
- **First common first-parent ancestor**: collect the first-parent history of one branch into a set (`git rev-list --first-parent`), then walk the other branch's first-parent history one commit at a time and return the first commit found in the set. This preserves chronological order and finds the most recent common first-parent commit. If none found distinct from merge base, use merge base.
- **Commits on each side**: list non-merge commits since the first common first-parent for both branches.
- **Files changed**: `git diff --name-only <merge-base>...<ref>` for each side. Compute the set of overlapping files (changed on both sides).

### Parallel branch analysis (use subagents)

Spawn these concurrently:

- **Current branch analysis**: analyze the full diff of the current branch from the merge base. Infer: overall intent/purpose, key design decisions and patterns, data flow changes, important invariants/constraints, public API changes.
- **Source branch overlap analysis**: analyze the source branch's changes to the overlapping files only. Identify: structural/architectural changes, renamed modules or changed module paths, changed function signatures and return types, removed or added APIs, new patterns or idioms introduced.

### Report to user

Present a short topology summary: branch names, key commits, commit counts on each side, number of overlapping files. Note that in-depth analysis is running. No approval required yet.

## Phase 3: Initiate merge

- Run `git merge <source> --no-commit`
- If "Already up to date": note this and proceed to Phase 5 for verification.
- If clean merge (no conflicts): proceed to Phase 5.
- If conflicts: proceed to Phase 4.

Do not commit yet. The commit happens in Phase 8 after all verification.

## Phase 4: Conflict analysis and planning

### 4.1 Identify all conflicts

- List conflicted files: `git ls-files -u | awk '{print $4}' | sort -u`
- Find all conflict marker locations: `grep -rn '^<<<<<<< \|^=======\|^>>>>>>> ' <files>`
- List auto-merged files that were changed on both branches (overlapping files that are NOT in the unmerged list).

### 4.2 Parallel conflict analysis (use subagents)

For each conflicted file, spawn a subagent with:
- The file contents including conflict markers with surrounding context
- The relevant portions of both branch analyses from Phase 2
- Instructions to:
  - Enumerate each conflict region with line numbers and surrounding context
  - For each region: describe the current branch's intent, the source branch's intent, and classify as compatible/complementary/contradictory
  - Propose a concrete resolution that preserves both intents where possible
  - When both branches appended items to the end of a grouping (e.g., imports, list entries, function definitions) and there is no semantic reason to prefer a particular order, place the source branch's additions before the current branch's additions
  - If intents are contradictory, explain the trade-off and what will be lost

### 4.3 Auto-merge sanity check (parallel with 4.2)

Spawn a subagent to review auto-merged files that were changed on both branches. Check for:
- Stale imports or module paths (e.g., a module was renamed on one branch but the other branch added new references to the old path)
- Changed function signatures where callers weren't updated (missing/extra parameters)
- Changed return types affecting callers
- Other structural inconsistencies between the two branches' changes

Cross-reference with the source branch overlap analysis from Phase 2.

### 4.4 Group related conflicts

Once all subagent analyses are complete:
- Group related conflicts: multiple regions in the same file, cross-file conflicts affecting the same API or feature
- Note any auto-merge bugs that relate to the same conflict groups

### 4.5 Present plan and get approval (GATE)

Present a structured plan to the user:
- For each conflict group: the files and regions involved, intent from each branch, compatibility assessment, and proposed resolution
- Auto-merge bugs found with proposed fixes
- **Prominently flag any code that will be lost**: tests, helper functions, features, or other code that cannot be trivially preserved because it depends on APIs or infrastructure removed by the other branch. Explain why it can't be preserved and suggest follow-ups if appropriate.

Ask: "Approve this merge resolution plan? (yes/no)"
- If no: ask for edits or constraints, update the plan, and re-present.
- Do not proceed until approved.

## Phase 5: Apply resolutions

1. **Execute the approved plan**: edit files to resolve conflicts group by group. Apply fixes for auto-merge bugs. Stage resolved files with `git add`.

2. **Verify completeness**:
   - No conflict markers remain: `grep -rn '^<<<<<<< \|^=======\|^>>>>>>> '` should yield nothing.
   - No unmerged files: `git ls-files -u` should be empty.
   - If any remain, fix and re-check.

## Phase 6: Checks and tests

### 6.1 Discover project tooling

Examine the repository for standard check and test commands. Look for:
- Justfiles, Makefiles, package.json scripts, pyproject.toml, Cargo.toml, go.mod, pom.xml, build.gradle, .csproj files, CMakeLists.txt, etc.
- Common patterns: formatting, linting, type checking, static analysis, unit tests, integration tests.

Present the discovered commands to the user and confirm before running.

### 6.2 Run checks

Execute the confirmed check commands. If issues arise:
- Use subagents to analyze and propose minimal fixes consistent with the merge plan.
- Apply fixes and re-run until clean.

### 6.3 Run tests

Execute the confirmed test commands. If failures:
- Use subagents to analyze failures and propose fixes.
- Prefer localized changes that maintain both branches' intents.
- If a fix requires significant changes, return to the user with options.
- Re-run until all tests pass.

All fixes in this phase are part of the merge. Keep changes minimal and consistent with the intent-preservation plan.

## Phase 7: Verification (GATE)

Goal: ensure both original branch intents are preserved in the merged result.

### Parallel verification (use subagents)

Spawn concurrently:
- **Verify current branch intent**: compare the merged result against the current branch analysis from Phase 2. Verify key invariants, data flows, APIs, and behaviors are preserved. Flag any discrepancies or removed functionality.
- **Verify source branch intent**: compare the merged result against the source branch overlap analysis from Phase 2. Ensure structural changes, renamed modules, changed signatures, and new patterns are correctly integrated. Verify callers were updated and imports are correct.

Reason step-by-step where deep semantic reasoning is needed.

### Present verification results and get approval (GATE)

Present a verification report:
- What is preserved from each branch
- Any discrepancies or regressions found
- Any remaining TODOs or follow-ups needed

Ask: "Accept the merged result as correct and complete? (yes/no)"
- If no: address issues, re-run Phase 6 checks/tests if needed, then re-verify.
- Iterate until approved.

## Phase 8: Commit

1. **Stage**: `git add -A`
2. **Commit**: `git commit -m "Merge branch '<source-branch>' into <current-branch>"`
3. **Post-commit**:
   - If a stash was created in Phase 1, remind the user about it.
   - Do not push automatically. Ask if the user wants to push.

## Error handling

- If any Git command fails unexpectedly, surface the error and ask the user how to proceed.
- If pre-checks find unsafe conditions and the user declines remediation, stop safely.
- If issues cannot be resolved without large refactors beyond the merge scope, present options:
  - Adjust the plan to selectively integrate parts
  - Postpone the merge and document follow-ups
  - Abort: `git merge --abort`
