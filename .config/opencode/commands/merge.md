---
description: Merge a source branch into the current branch with deep analysis, parallel conflict resolution, and full verification
---

# Merge Branch

**Source branch:** $1

Merge the specified source branch into the current branch. This command is repo-agnostic and must be run from inside a Git repository.

## Principles

- Use the `task` tool aggressively to parallelize analysis work across files and branches.
- The main agent is an orchestrator and user-facing decision-maker. Delegate data-heavy work (git output processing, file reading/editing, test execution, diff analysis) to subagents so that raw outputs stay out of the main context. Subagents return concise structured summaries.
- **Subagent branch awareness**: The main working tree reflects the **current branch** only. When a subagent needs to analyze source branch content, prefer subagents with bash/git access so they can run git commands directly. When choosing between subagent types, always prefer ones that support bash or git over ones that can only read files. A temporary checkout of the source branch (set up in Phase 2) provides a filesystem path that any subagent type can read, and ensures file-reading-only subagents see the correct branch's content.
- Think carefully and reason step-by-step for complex or ambiguous decisions that benefit from deeper consideration.
- Never assume project tooling. Discover check/test commands and confirm with the user.
- Present plans before making changes that affect code content. Require explicit approval at gates.
- Even clean merges get full analysis and verification.
- Be explicit about any code that will be lost or cannot be trivially preserved.

If $1 is not provided, ask the user to supply a branch name.

## Phase 1: Pre-checks (use subagent)

Spawn a subagent to run all pre-check commands and return a structured summary. The subagent performs:

1. **Verify Git repo**: `git rev-parse --show-toplevel`. If not in a repo, return an error.

2. **Resolve refs**:
   - Current branch: `git rev-parse --abbrev-ref HEAD`
   - Source branch: verify $1 exists as a local branch, remote-tracking branch, or valid ref. Report if ambiguous or missing.

3. **Check for in-progress operations**:
   - Check for ongoing merge (`git rev-parse -q --verify MERGE_HEAD`), rebase (`.git/rebase-apply`, `.git/rebase-merge`), cherry-pick (`.git/CHERRY_PICK_HEAD`), or revert (`.git/REVERT_HEAD`).

4. **Verify clean working tree**:
   - `git status --porcelain`

5. **Fetch and verify upstream freshness**:
   - `git fetch --all --prune --tags`
   - For each branch (current and source): check if it has an upstream and whether it is behind.

The subagent returns a structured report containing: repo root, current branch name, resolved source ref, working tree status (clean or list of dirty files), in-progress operations (if any), and upstream freshness for both branches (ahead/behind counts).

The main agent reviews the summary and handles any user decisions:
- If not in a repo: stop with a clear message.
- If source ref is ambiguous or missing: ask the user to clarify.
- If in-progress operations found: ask the user whether to abort and restart, or bail out.
- If working tree not clean: ask the user to stash, commit, or stop.
- If current branch is behind upstream: ask the user to fast-forward first.
- If source branch is behind upstream: offer to merge the upstream ref instead, update the local branch, or stop.

Once all issues are resolved, state the current branch, the resolved source ref, and proceed.

## Phase 2: Branch topology and initial research

Goal: build a thorough understanding of both branches before merging.

### Set up source branch checkout

Create a temporary directory containing a checkout of the source branch so that subagents can read the source branch's actual file contents (not the current branch's working tree). If the repository is inside a git worktree, use `git worktree add`; otherwise, use an alternative approach (e.g., `git clone --shared --branch <source>` into a temp directory).

Record the path. Pass it to any subagent that needs to read source branch files. This checkout persists until cleanup in Phase 8.

### Parallel research (use subagents)

Spawn all three concurrently:

- **Topology analysis**: compute the full branch topology and return a concise structured summary. The subagent performs:
  - **Merge base**: `git merge-base HEAD <source>`
  - **First common first-parent ancestor**: collect the first-parent history of one branch into a set (`git rev-list --first-parent`), then walk the other branch's first-parent history one commit at a time and return the first commit found in the set. This preserves chronological order and finds the most recent common first-parent commit. If none found distinct from merge base, use merge base.
  - **Commits on each side**: list non-merge commits since the first common first-parent for both branches.
  - **Files changed**: `git diff --name-only <merge-base>...<ref>` for each side. Compute the set of overlapping files (changed on both sides).
  - Return: merge base SHA, first common first-parent SHA, commit counts on each side, list of overlapping files, and a brief summary of the commit topics on each side. Do not return raw commit lists.

- **Current branch analysis**: analyze the full diff of the current branch from the merge base. Infer: overall intent/purpose, key design decisions and patterns, data flow changes, important invariants/constraints, public API changes.

- **Source branch overlap analysis**: analyze the source branch's changes to the overlapping files only (the topology subagent independently computes the overlapping file set; this subagent should also compute it). **Direct the subagent to read files from the source branch checkout path** (not the main working tree, which contains the current branch). Identify: structural/architectural changes, renamed modules or changed module paths, changed function signatures and return types, removed or added APIs, new patterns or idioms introduced.

### Report to user

Present a short topology summary from the topology subagent's results: branch names, key commits, commit counts on each side, number of overlapping files. Note that in-depth analysis is running (or complete). No approval required yet.

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
- **Separate lock files**: Identify any conflicted files matching known lock file patterns (`Cargo.lock`, `poetry.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.json`, `composer.lock`, `Gemfile.lock`, `go.sum`, `packages.lock.json`, etc.). By default these files cannot be meaningfully hand-merged and will be checked out from a chosen branch instead. Present the list and ask the user how to handle them. First offer a single choice for all lock files:
  - **Source branch (`<source>`)** (Recommended) — check out the source branch's version; typical when catching up (e.g., merging `main` into a feature branch)
  - **Current branch (`HEAD`)** — check out the current branch's version; typical when the current branch has the more authoritative dependency state
  - **Choose per file** — decide individually for each lock file

  If the user selects "Choose per file", present each lock file with the options:
  - **Source branch (`<source>`)**
  - **Current branch (`HEAD`)**
  - **Merge manually** — keep this file in the conflict set and resolve it through the normal conflict analysis and resolution process

  Exclude lock files from the per-file conflict analysis in 4.2 unless the user opted to merge them manually.

### 4.2 Parallel conflict analysis (use subagents)

(Lock files identified in 4.1 are excluded from this analysis unless the user opted to merge them manually.)

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

Spawn a subagent to review auto-merged files that were changed on both branches. **Direct the subagent to read source branch files from the source checkout path** to compare against the merged result in the main working tree. Check for:
- Stale imports or module paths (e.g., a module was renamed on one branch but the other branch added new references to the old path)
- Changed function signatures where callers weren't updated (missing/extra parameters)
- Changed return types affecting callers
- Other structural inconsistencies between the two branches' changes

Cross-reference with the source branch overlap analysis from Phase 2.

### 4.4 Group related conflicts and synthesize plan (use subagent)

Once all subagent analyses from 4.2 and 4.3 are complete, spawn a single **planner subagent** to synthesize the results. Pass it the raw outputs from all per-file conflict analyses (4.2) and the auto-merge sanity check (4.3). The planner subagent:

- Groups related conflicts: multiple regions in the same file, cross-file conflicts affecting the same API or feature
- Notes any auto-merge bugs that relate to the same conflict groups
- Produces a structured resolution plan containing, for each conflict group:
  - The files and regions involved
  - Intent from each branch and compatibility assessment
  - Proposed resolution
  - Auto-merge bugs found with proposed fixes
- **Prominently flags any code that will be lost**: tests, helper functions, features, or other code that cannot be trivially preserved because it depends on APIs or infrastructure removed by the other branch. Explains why it can't be preserved and suggests follow-ups if appropriate.

The planner subagent returns the structured plan. The main agent does not process the raw per-file analyses directly.

### 4.5 Present plan and get approval (GATE)

Present the planner subagent's structured plan to the user, adding:
- **Lock file resolution**: the conflicted lock files and the chosen source branch for each. Note that regeneration is left to the user or repository tooling (e.g., pre-commit hooks). Any lock files the user opted to merge manually are included in the conflict groups above.

Ask: "Approve this merge resolution plan? (yes/no)"
- If no: ask for edits or constraints, update the plan, and re-present.
- Do not proceed until approved.

## Phase 5: Apply resolutions (use subagents)

1. **Execute the approved plan in parallel**: for each conflict group in the approved plan, spawn a subagent to apply the resolution. Each subagent receives its group's resolution details (files, regions, proposed edits, auto-merge fixes) and:
   - Edits the assigned files to resolve conflicts
   - Applies fixes for auto-merge bugs in its group
   - Stages resolved files with `git add`
   - Lock files marked for manual merge that fall within the group are resolved as part of this step
   - Returns a summary of changes made

   Run independent conflict groups in parallel. If groups share files, run them sequentially.

2. **Resolve lock files**: For each lock file not marked for manual merge, run `git checkout <chosen-branch> -- <lock-file>` then `git add <lock-file>`. Do not attempt to regenerate lock files — that is left to the user or repository tooling (e.g., pre-commit hooks).

3. **Verify completeness**:
   - No conflict markers remain: `grep -rn '^<<<<<<< \|^=======\|^>>>>>>> '` should yield nothing.
   - No unmerged files: `git ls-files -u` should be empty.
   - If any remain, fix and re-check.

## Phase 6: Checks and tests

### 6.1 Discover project tooling (use subagent)

Spawn a subagent to examine the repository for standard check and test commands. The subagent scans for:
- Justfiles, Makefiles, package.json scripts, pyproject.toml, Cargo.toml, go.mod, pom.xml, build.gradle, .csproj files, CMakeLists.txt, etc.
- Common patterns: formatting, linting, type checking, static analysis, unit tests, integration tests.

The subagent returns a categorized list of discovered commands (checks vs. tests) with brief descriptions. Present the discovered commands to the user and confirm before running.

### 6.2 Run checks (use subagents)

For each confirmed check command, spawn a subagent to execute it. Each subagent:
- Runs the command and captures full output
- Returns a pass/fail status with only the relevant failure excerpts (not the full output)

If issues arise:
- Use subagents to analyze failures and propose minimal fixes consistent with the merge plan.
- Apply fixes and re-run until clean.

### 6.3 Run tests (use subagents)

For each confirmed test command, spawn a subagent to execute it. Each subagent:
- Runs the command and captures full output
- Returns a pass/fail status with only the relevant failure excerpts (test names, error messages, stack traces) — not the full output

If failures:
- Use subagents to analyze failures and propose fixes.
- Prefer localized changes that maintain both branches' intents.
- If a fix requires significant changes, return to the user with options.
- Re-run until all tests pass.

All fixes in this phase are part of the merge. Keep changes minimal and consistent with the intent-preservation plan.

## Phase 7: Verification (GATE)

Goal: ensure both original branch intents are preserved in the merged result.

### Parallel verification and diff generation (use subagents)

Spawn all three concurrently:

- **Verify current branch intent**: compare the merged result against the current branch analysis from Phase 2. Verify key invariants, data flows, APIs, and behaviors are preserved. Flag any discrepancies or removed functionality. Reason step-by-step where deep semantic reasoning is needed.

- **Verify source branch intent**: compare the merged result against the source branch overlap analysis from Phase 2. Ensure structural changes, renamed modules, changed signatures, and new patterns are correctly integrated. Verify callers were updated and imports are correct. Reason step-by-step where deep semantic reasoning is needed.

- **Generate diff files**: create a temporary directory (`mktemp -d --tmpdir merge-diff-XXXXXX`), save the before diff (`git diff <source>...HEAD > $tmpdir/before.diff`), save the after diff (`git diff <source> > $tmpdir/after.diff`), and return the quoted paths (using `printf '%q'`).

### Present verification results and get approval (GATE)

Present a verification report combining the subagent results:
- What is preserved from each branch
- Any discrepancies or regressions found
- Any remaining TODOs or follow-ups needed
- Diff file paths from the diff generation subagent:
  ```
  Diff files saved:
    <quoted-path>/before.diff <quoted-path>/after.diff
  ```

Ask: "Accept the merged result as correct and complete? (yes/no)"
- If no: address issues, re-run Phase 6 checks/tests if needed, then re-verify.
- Iterate until approved.

## Phase 8: Commit

1. **Stage**: `git add -A`
2. **Commit**: `git commit -m "Merge branch '<source-branch>' into <current-branch>"`
3. **Clean up source checkout**: Remove the temporary source branch checkout created in Phase 2 (e.g., `git worktree remove <path>` or `rm -rf <path>` depending on the method used).
4. **Post-commit**:
   - If a stash was created in Phase 1, remind the user about it.
   - Do not push automatically. Ask if the user wants to push.

## Error handling

- If any Git command fails unexpectedly, surface the error and ask the user how to proceed.
- If pre-checks find unsafe conditions and the user declines remediation, stop safely.
- If issues cannot be resolved without large refactors beyond the merge scope, present options:
  - Adjust the plan to selectively integrate parts
  - Postpone the merge and document follow-ups
  - Abort: `git merge --abort`
- Always clean up the temporary source branch checkout on abort or early exit.
