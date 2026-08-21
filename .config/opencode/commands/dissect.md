---
description: Rebuild a change as an explanatory DAG of reviewable commits
---

# Dissect Changes

**Arguments:** $ARGUMENTS

Execute this workflow interactively in the current Git repository. The goal is
to reconstruct an existing change as a set of small, explanatory commits and
branches whose integrated tree is exactly the same as the original target.
The reconstruction may be a DAG: independent pieces should remain parallel,
while pieces that require earlier work should build on those prerequisite
branches.

Prioritize review structure and explanatory value over code validation. A piece
is allowed to be an intermediate review step that does not compile, lint, or
pass tests. Exact final-tree equivalence is still required because it proves the
dissection represents the requested change; it is not a substitute for, or a
request to perform, build and test validation.

## Invocation

Accept these input forms:

```text
/dissect
/dissect <base-revision> <target-revision> [guidance]
/dissect <base-revision> --patch <patch-file> [guidance]
/dissect <base-revision>..<target-revision> [guidance]
/dissect <default-branch>...<target-revision> [guidance]
```

Treat additional text as guidance about useful boundaries, ordering, naming,
or reviewer concerns. Do not interpolate argument text into shell commands.
Resolve and validate revisions and paths separately before using them.

With no arguments, default to `<default-branch>...HEAD`. Detect the default
branch from the symbolic remote HEAD, preferring `upstream` and then `origin`,
and fall back to an unambiguous local `main`, `master`, or `dev`. For three-dot
input, resolve the reconstruction base with `git merge-base <left> <right>` and
use the right side as the target; this matches the tree change selected by
`git diff <left>...<right>`. Report the detected default branch and resolved
merge base before presenting the DAG.

If the default branch cannot be determined unambiguously, or an explicit input
is ambiguous, inspect the current branch, its upstream, and the working tree,
then ask the user which base and target to use. Do not guess when multiple
interpretations are plausible.

For a patch file, create a temporary target branch from the base in an isolated
worktree, apply the patch including binary changes, and commit it. This commit
is only the immutable target used for comparison; do not use it as a parent of
the reconstructed pieces. If the patch does not apply cleanly, stop and explain
the failure.

## Safety Rules

- Before doing work, confirm that the active agent can run shell commands,
  create commits, and modify branches. In plan or read-only mode, stop and ask
  the user to switch to the build agent and rerun the command.
- Never modify, reset, rebase, delete, or check out the user's source branches.
- Never push branches or commits.
- Never force-update a branch.
- Perform construction in temporary worktrees under `/tmp/opencode`, not in the
  user's current worktree. Existing uncommitted changes in the current worktree
  must remain untouched.
- Put every created branch under `dissect/`.
- Before creating anything, list colliding `dissect/` branches and worktrees.
  If names collide, offer to continue the prior dissection, choose another run
  name, or rebuild. Deleting or replacing prior work requires explicit approval.
- Record the original current branch, HEAD, status, and worktree list. Verify at
  completion that the original worktree still has the same branch, HEAD, and
  status.
- Remove temporary worktrees when finished, but preserve all resulting branches.

## Phase 1: Resolve the Change

1. Resolve the base and target to full commit IDs with `git rev-parse --verify`.
2. Verify both objects are commits. For patch input, materialize the target as
   described above.
3. Determine whether the base is an ancestor of the target. If it is not, show
   the merge base and ask whether the user intends a direct two-tree comparison
   or wants the merge base as the base.
4. Capture the target tree ID with `git rev-parse <target>^{tree}`. This tree ID
   is the definitive success criterion.
5. Gather the complete binary-safe diff, diff statistics, changed paths,
   relevant commit history, and enough surrounding source context to understand
   the change. Renames and mode changes must not be lost.
6. Choose a short, filesystem-safe run name. Default to the target's short hash,
   optionally prefixed by a sanitized target branch name when that adds clarity.

Use these branch conventions:

```text
dissect/<run>/<piece>
dissect/<run>/result
dissect/<run>/target       # only when a patch must be materialized
```

## Phase 2: Design the DAG

Analyze the entire final diff before constructing commits. Group changes by
reviewable intent rather than merely by file. A useful piece should explain one
coherent idea and should be independently understandable at its point in the
graph.

Reserve these mechanical categories instead of mixing them into the substantive
review pieces:

- `imports`: import-only changes from any file;
- `tests`: all test changes, including test support code, fixtures, and test
  configuration, but excluding import-only hunks assigned to `imports`;
- `cruft`: optional low-value mechanical residue such as incidental formatting,
  generated metadata, or unrelated housekeeping that is necessary for exact
  tree equivalence but does not help explain the substantive change.

Do not classify a change as `cruft` merely because it is difficult to explain.
List the proposed cruft scope explicitly and ask the user when classification is
uncertain. These categories become trailing standalone commits after the
substantive DAG has been integrated; they are not part of the recommended
review path.

For each proposed piece identify:

- a concise branch slug and commit subject;
- a draft Markdown review guide for the commit message;
- its direct prerequisite pieces, if any;
- the exact files and hunks it owns;
- why those changes belong together;
- any overlap or likely merge conflict with another piece.

Prefer independent root pieces when no real dependency exists. Introduce a
dependency when a piece cannot be represented or understood sensibly without
another piece. Do not add dependencies merely to make every intermediate piece
compile or pass tests. Avoid artificial linearization.

Present the proposed DAG before creating piece branches. Include a topological
list and a text graph, plus the scope and rationale for each node. Format the
graph like `git log --graph`: show one proposed commit per row, put topology
lines on the left, and put the subject on that row. Do not use an abstract
node-and-arrow diagram. Show the reserved `imports`, `tests`, and optional
`cruft` commits as a linear tail after substantive integration. Ask the user to
approve or revise it. Do not begin branch construction until approved.

## Phase 3: Construct the Pieces

Create each piece in topological order using isolated temporary worktrees:

1. A root piece starts at the exact base commit.
2. A piece with one prerequisite starts at that prerequisite branch.
3. A piece with multiple prerequisites starts from one prerequisite and merges
   the others before adding its own change. If this obscures reviewability,
   introduce an explicit integration node and explain it.
4. Apply only the target changes assigned to this piece. Use the immutable
   target tree as the source of truth. Whole-file restoration is appropriate
   only when the whole target-side file belongs to the piece; otherwise apply
   selected hunks or make exact edits and verify their diff.
5. Preserve renames, executable bits, symlinks, binary content, and deletions.
6. Inspect the staged diff before committing and confirm it matches the planned
   scope. Do not include temporary files or generated explanations in the tree.
7. Commit with a concise subject and a Markdown body written as a guide through
   that commit's actual diff. Use short sections where useful, such as
   `## Purpose`, `## Review guide`, and `## Dependencies`. Explain the intent,
   tell the reviewer what files, symbols, or hunks to read and in what order,
   call out important implementation details, and describe how the piece
   relates to its prerequisites. Omit sections that add no value. The message
   must stand on its own in GitHub's commit view and must not narrate the
   mechanics of splitting the original diff.
8. Do not run builds, linters, tests, or other code-validation commands unless
   the user explicitly requests them. Spend that effort improving the review
   boundaries, explanations, and reading order instead.

The reserved trailing categories are exempt from the Markdown review-guide
requirement. Do not create them during substantive piece construction, and do
not pad their commit messages with explanations nobody is expected to review.

If construction reveals that the proposed grouping is wrong, stop, explain the
new evidence, and propose a DAG revision. Get confirmation before replacing
already-created branches.

## Phase 4: Integrate the DAG

Create `dissect/<run>/result` from the base and merge the piece branches in a
topological order that respects dependencies. Do not merge both a prerequisite
and its descendant when the descendant already contains the prerequisite,
unless another leaf requires the prerequisite independently.

Resolve only mechanical merge conflicts whose intended result is unambiguous
from the target tree. If conflict resolution would introduce substantive code
not owned by a piece, revise the graph or the responsible piece instead of
hiding that code in the merge commit.

Give every non-trivial integration merge a Markdown commit body that tells the
reviewer which parent pieces are being combined, why they can now be considered
together, and where to continue the review. Do not use Git's default merge
message as the entire explanation.

After all substantive leaves are integrated, append the reserved changes to the
result branch as standalone commits in this order:

1. `imports`, containing only import changes;
2. `tests`, containing all remaining test-related changes;
3. `cruft`, when any confirmed cruft remains.

Omit an empty category. Use the category name as the commit subject. Keep these
commits separate even when combining them would reduce the commit count. Do not
place substantive implementation changes in this trailing sequence.

## Phase 5: Prove Equivalence and Iterate

Compare the reconstructed result with the original target in both ways:

```text
git rev-parse dissect/<run>/result^{tree}
git rev-parse <target>^{tree}
git diff --binary --stat <target> dissect/<run>/result
git diff --binary --exit-code <target> dissect/<run>/result
```

Success requires identical tree IDs and an empty diff. Commit IDs are expected
to differ.

If the trees differ:

1. Inspect the complete residual diff.
2. Attribute every discrepancy to the piece that conceptually owns it.
3. Update that piece and any descendants affected by the update.
4. Rebuild the result branch without force-updating or deleting prior work
   unless the user explicitly approves replacement. Prefer correction commits
   during early iteration so the history of the attempt remains inspectable.
5. Repeat the tree-equivalence comparison until the trees are identical.

Do not create a generic "remaining changes" or "make trees match" commit unless
the user explicitly chooses that tradeoff after seeing the residual diff. Exact
equivalence achieved by an unexplained catch-all is not a successful
dissection.

## Phase 6: Report

Report:

- the resolved base, target, and target tree ID;
- the final graph, generated from the resulting Git history with
  `git log --graph --oneline --decorate --date-order <base>..<result>`, with one
  commit per row and topology lines on the left;
- each piece's reviewer-facing explanation and prerequisites;
- the scope placed in the trailing `imports`, `tests`, and `cruft` commits;
- the result branch and its tree ID;
- whether exact tree equality was proven;
- any correction commits, unresolved concerns, or intentionally imperfect
  boundaries;
- confirmation that the original worktree was left unchanged.

Do not supplement or replace the final graph with an abstract node-and-arrow
diagram. End with a suggested review order that stops before the trailing
`imports`, `tests`, and `cruft` commits. Do not push anything.

The final item in the response must be a copy-pastable Tig command that shows
only commits reachable from the dissection result and not from its base. Use the
resolved base commit and actual result branch name:

```text
tig <base>..dissect/<run>/result
```

Put this command in a fenced code block and output no text after it.
