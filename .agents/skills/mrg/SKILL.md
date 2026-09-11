---
name: mrg
description: Perform a lightweight merge of a source branch into the current branch with basic safety checks and optional tests. Use for simple or routine merges; escalate broad, architectural, or semantically risky conflicts to the full merge skill.
---

# Light Merge

**Source branch:** Read the branch or ref from the user's request. Use `<source>` below for that resolved ref.

Merge the specified source branch into the current branch using a lightweight,
pragmatic workflow. This skill is for simple or routine merges. If conflicts
become broad, architectural, or semantically risky, pause and recommend rerunning
with the `merge` skill instead.

If the request does not identify a source branch, ask the user to supply one.

## Principles

- Keep the workflow fast and local. Do not perform deep branch topology analysis
  unless a concrete problem requires it.
- Do not create temporary worktrees or source checkouts by default.
- Do not use subagents by default. Use the current host's available subagent
  tools only when conflict analysis becomes noisy enough that delegating would
  materially improve clarity; if unavailable, analyze locally.
- Do not assume project tooling. Offer checks/tests when discovered or obvious,
  but do not require them for simple merges.
- Do not commit or push without explicit user approval.
- Never revert unrelated working tree changes.

## Phase 1: Basic Safety Checks

Run these checks directly from the current repository:

1. Verify this is a Git repository:
   `git rev-parse --show-toplevel`
2. Identify the current branch:
   `git branch --show-current`
3. Verify the source ref exists:
   `git rev-parse --verify --quiet <source>^{commit}`
4. Check for in-progress Git operations:
   - `git rev-parse -q --verify MERGE_HEAD`
   - Check `.git/rebase-apply`, `.git/rebase-merge`, `.git/CHERRY_PICK_HEAD`,
     and `.git/REVERT_HEAD` when needed.
5. Verify the working tree is clean:
   `git status --porcelain`

Stop and ask the user how to proceed if:

- Not inside a Git repository.
- The source ref is missing or ambiguous.
- A merge, rebase, cherry-pick, or revert is already in progress.
- The working tree has uncommitted changes.

Fetching is optional. Do not run `git fetch --all` by default. If the source ref
is remote-tracking or freshness matters, ask whether to fetch first.

## Phase 2: Start Merge

Run:

```sh
git merge <source> --no-commit
```

Then inspect the result:

- If Git reports "Already up to date", report that and stop.
- If the merge applies cleanly, continue to Phase 4.
- If conflicts occur, continue to Phase 3.

Do not commit yet.

## Phase 3: Resolve Conflicts

First summarize the conflict state:

```sh
git status --short
git ls-files -u
```

List conflicted files and inspect the conflict markers in those files.

Handle conflicts according to complexity:

- For obvious, localized conflicts, resolve them directly with minimal edits.
- **Separate lock files first**: identify conflicted lock files (`Cargo.lock`,
  `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `go.sum`,
  `Gemfile.lock`, etc.) before editing anything else. By default, do not
  hand-merge generated lock files.
- For lock files, present the list and ask the user how to handle them. First
  offer a single choice for all lock files:
  - **Source branch (`<source>`)** (Recommended) — check out the source branch's
    version; typical when catching up (for example, merging `main` into a
    feature branch)
  - **Current branch (`HEAD`)** — check out the current branch's version; use
    this when the current branch has the authoritative dependency state
  - **Choose per file** — decide individually for each lock file

  If the user selects "Choose per file", present each lock file with these
  options:
  - **Source branch (`<source>`)**
  - **Current branch (`HEAD`)**
  - **Leave for manual/tool regeneration** — do not hand-edit the file in the
    merge workflow; let the user or repository tooling regenerate it later
  - **Merge manually** — keep this file in the conflict set and resolve it like
    a normal file only if the user explicitly chooses that path

  Exclude lock files from direct conflict editing unless the user explicitly
  chooses manual merge for a specific file.
- For ambiguous semantic conflicts, explain the trade-off and ask the user before
  editing.
- If conflicts span many files, changed APIs, renamed modules, or architectural
  decisions, stop and recommend using the `merge` skill for the full analysis workflow.

After resolving conflicts:

1. For each lock file not left for manual/tool regeneration and not manually
   merged, resolve it by checking out the chosen branch's version, then stage
   it with `git add <lock-file>`.
2. Stage other resolved files with `git add <files>`.
3. Verify no unmerged files remain:
   `git ls-files -u`
4. Verify no conflict markers remain in edited files. Search for:
   `<<<<<<<`, `=======`, and `>>>>>>>`.

If conflict markers or unmerged entries remain, fix them before continuing.

## Phase 4: Summarize Result

Show a concise merge summary:

```sh
git status --short
git diff --stat --cached
git diff --stat
```

Explain:

- Whether the merge was clean or required conflict resolution.
- Which files were changed.
- Any decisions made while resolving conflicts.
- Any unresolved risks or follow-up items.

## Phase 5: Optional Verification

Offer to run checks or tests if there are obvious commands from repository files
or recent project conventions. Examples include `just test`, `make test`,
`npm test`, `cargo test`, `pytest`, or project-specific scripts.

Do not perform broad tooling discovery unless the user asks or the merge touched
areas where verification is clearly warranted.

If checks/tests fail, diagnose and apply minimal fixes only when the failure is
clearly caused by the merge. Otherwise report the failure and ask how to proceed.

## Phase 6: Commit Or Leave Uncommitted

Ask the user what to do next:

- Commit the merge.
- Leave the merge staged/uncommitted for review.
- Run additional checks/tests.
- Abort the merge with `git merge --abort`.

Only commit after explicit approval. Use:

```sh
git commit -m "Merge branch '<source>' into <current-branch>"
```

Do not push automatically. If the user asks to push, use a normal `git push` and
never force push unless explicitly requested.

## Error Handling

- If any Git command fails unexpectedly, show the error and ask how to proceed.
- If the lightweight workflow no longer fits the conflict complexity, stop and
  recommend the `merge` skill rather than improvising a deep merge process inline.
- If the user chooses to abort, run `git merge --abort` only when a merge is in
  progress.
