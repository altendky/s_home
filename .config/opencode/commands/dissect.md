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
worktree, apply the patch including binary changes, and commit it with
`--no-verify`. This commit is only the immutable target used for comparison; do
not use it as a parent of the reconstructed pieces or include it in result
commit numbering. If the patch does not apply cleanly, stop and explain the
failure.

## Safety Rules

- Before doing work, confirm that the active agent can run shell commands,
  create commits, and modify branches. In plan or read-only mode, stop and ask
  the user to switch to the build agent and rerun the command.
- Never modify, reset, rebase, delete, or check out the user's source branches.
- Do not push by default. The only exception is the opt-in publication phase,
  after local completion and two explicit user decisions. Even then, push only
  the result branch with a normal non-forced push.
- Never force-update a branch.
- Create every commit and merge with `--no-verify`. Do not run pre-commit,
  commit-message, or merge hooks manually; they are outside the scope of review
  decomposition and can waste time or introduce unrelated failures.
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

### Mirrored representations

Look for relationships where one contract, schema, enum, wire type, constant
set, or data model is duplicated in another language or layer. Search changed
files and nearby code for evidence such as `keep in sync`, `mirrors`,
`generated from`, matching discriminants, serialization names, generation
scripts, documentation, or corresponding symbol names.

Treat defining the canonical contract and synchronizing its mirrors as separate
reviewer concerns:

- identify which representation is canonical when the repository establishes
  one;
- put the canonical definition in its substantive commit;
- put each manually synchronized representation in a dependent follow-up
  commit, with a subject such as `Synchronize TypeScript wire-type mirror`;
- explain in the mirror commit which definition it follows and what values or
  behavior must remain synchronized;
- combine multiple mirrors only when they are mechanical representations of the
  same canonical definition and remain clearer together.

Mirrored contract changes carry compatibility risk and must not be classified
as `cruft`, even when repetitive. Do not infer a mirror relationship solely
because two changed definitions look similar. If comments, scripts,
documentation, naming, or repository history do not establish the relationship,
mark it as a suspected mirror in the proposed DAG and ask the user.

For each proposed piece identify:

- a concise branch slug and commit subject;
- a draft Markdown review guide for the commit message;
- its direct prerequisite pieces, if any;
- the final target files and hunks it ultimately explains;
- any intermediate-only edits or placement used to improve diff readability;
- any canonical or mirrored representations it defines or synchronizes;
- why those changes belong together;
- any overlap or likely merge conflict with another piece.

Prefer independent root pieces when no real dependency exists. Introduce a
dependency when a piece cannot be represented or understood sensibly without
another piece. Do not add dependencies merely to make every intermediate piece
compile or pass tests. Avoid artificial linearization.

Optimize the readability of each individual diff, not merely the partitioning
of the final target diff. An intermediate tree does not have to be a strict
subset of the target tree. It may temporarily arrange code differently from
both the base and target when that makes a transformation substantially easier
to recognize. For example, when extracting reusable logic to a distant final
location, first extract it beside the original caller so the movement and
behavior preservation are obvious, then move it to its final location in a
separate dependent commit.

Keep review-oriented transitions minimal and purposeful. Give each transition
its own commit, identify the temporary state in the commit message, and point
the reviewer to the follow-up that reaches the final arrangement. Do not create
gratuitous churn. These transitions are substantive parts of the review
narrative and must not be classified as `cruft`.

Present the proposed DAG before creating piece branches. Include a topological
list and a text graph, plus the scope and rationale for each node. Format the
graph like `git log --graph`: show one proposed commit per row, put topology
lines on the left, and put the subject on that row. Do not use an abstract
node-and-arrow diagram. Show the reserved `imports`, `tests`, and optional
`cruft` commits as a linear tail after substantive integration. Ask the user to
approve or revise it. Do not begin branch construction until approved.

### Commit numbering

Prefix every commit subject that will be reachable from the result but not from
the base with its position and the total result commit count:

```text
[03/12] Extract reusable request parsing
```

Pad each number to the width of the total. The total includes substantive,
review-oriented transitional, integration merge, `imports`, `tests`, and
`cruft` commits. It excludes the base, original target history, and a
materialized patch-target commit.

Number commits in intended review and creation order, with every parent before
its descendants. GitHub's pull-request Commits tab presents commits oldest
first according to their chronological order in the head branch, but parallel
siblings in a DAG have no intrinsic total order. Create independent siblings
and merge branches in the intended review order, and use this deterministic
local order as the numbering reference:

```text
git rev-list --reverse --topo-order <base>..<result>
```

Include the proposed number in each row of the DAG shown for approval. Freeze
the expected commit count before construction. If iteration adds, removes, or
reorders commits, renumber the complete generated result history before
declaring completion.

## Phase 3: Construct the Pieces

Create each piece in topological order using isolated temporary worktrees:

1. A root piece starts at the exact base commit.
2. A piece with one prerequisite starts at that prerequisite branch.
3. A piece with multiple prerequisites starts from one prerequisite and merges
   the others before adding its own change. If this obscures reviewability,
   introduce an explicit integration node and explain it.
4. Construct the target changes assigned to this piece, plus any approved
   intermediate-only edits that improve its diff. Use the immutable target tree
   as the source of truth for the final arrangement, not as a restriction that
   every intermediate tree must be its subset. Whole-file restoration is
   appropriate only when the whole target-side file belongs to the piece;
   otherwise apply selected hunks or make deliberate edits and verify their
   diff.
5. Preserve renames, executable bits, symlinks, binary content, and deletions.
6. Inspect the staged diff before committing and confirm it matches the planned
   scope. Do not include temporary files or generated explanations in the tree.
7. Commit with `git commit --no-verify`, using the numbered concise subject and
   a Markdown body written as a guide through that commit's actual diff. Use
   short sections where useful, such as
   `## Purpose`, `## Review guide`, and `## Dependencies`. Explain the intent,
   tell the reviewer what files, symbols, or hunks to read and in what order,
   call out important implementation details, and describe how the piece
   relates to its prerequisites. Omit sections that add no value. The message
   must stand on its own in GitHub's commit view and must not narrate the
   mechanics of splitting the original diff. When the commit intentionally
   creates a temporary review-oriented arrangement, explain that arrangement
   and name the follow-up step that moves it toward the target.
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
unless another leaf requires the prerequisite independently. Use
`git merge --no-verify` for every merge.

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

Omit an empty category. Use the category name as the subject text after its
numbering prefix. Keep these commits separate even when combining them would
reduce the commit count. Do not place substantive implementation changes in
this trailing sequence. Create each trailing commit with
`git commit --no-verify`, for example `[11/12] tests`.

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

### Reviewer simulation and refinement

After first proving tree equivalence, perform at least one complete review of
the reconstructed history as if encountering it for the first time. Do not
proceed directly from initial equivalence to numbering verification or
publication.

Inspect the actual result rather than the earlier plan:

```text
git log --graph --oneline --decorate --topo-order <base>..<result>
git log --reverse --topo-order --format='%H %s' <base>..<result>
git diff <commit>^1 <commit>
git diff <commit>^2 <commit>   # also inspect the other parent of a merge
```

Read every commit message immediately before its parent diff. Evaluate:

- whether the purpose and suggested reading order are obvious without relying
  on later commits;
- whether each commit contains one coherent reviewer concern;
- whether extractions, moves, and reuse are presented clearly enough to
  recognize behavior preservation;
- whether temporary review-oriented arrangements improve clarity and have an
  understandable follow-up;
- whether canonical definitions and mirrored representations are separated;
- whether dependencies are real rather than artifacts of construction;
- whether a large commit should be split or adjacent small commits combined;
- whether `imports`, `tests`, and `cruft` contain only their reserved mechanical
  changes;
- whether merge commits explain their parents and advance the review narrative.

When available, ask a fresh read-only reviewer subagent to inspect the graph,
messages, and commit diffs for clarity problems. Use it as an independent
perspective, not as a replacement for the main workflow's review.

If the pass finds concrete improvements to boundaries, ordering, explanations,
dependencies, or diff readability, present a concise refinement plan and get
approval before replacing generated branches. Apply the approved refinements,
rebuild affected descendants and the result, then re-prove exact tree
equivalence. Repeat the reviewer-simulation pass while it continues to find
material improvements. Stop when a full pass finds none; do not prolong the
workflow for subjective polish without a specific reviewer benefit.

After refinement is stable and tree equivalence has been re-proven, recount and
inspect the final history with:

```text
git rev-list --count <base>..<result>
git log --reverse --topo-order --format='%s' <base>..<result>
```

Verify that every result commit has one unique, contiguous prefix from 1 through
the total and that the denominator matches the actual count. If the displayed
topological order does not match the prefixes, or the graph changed during
iteration, renumber and rebuild the generated history. Do not complete with
stale or duplicate numbering.

## Phase 6: Optional Publication

Publication is never inferred from the arguments or conversation. After exact
tree equivalence and commit numbering are proven, briefly ask:

> Publish this as a draft dissection PR and link it from the original PR?

If the user declines, perform no publication discovery or network mutation and
continue to the report. If the user accepts, perform the following read-only
preflight. Acceptance of the brief offer authorizes discovery only, not remote
mutation.

### Discover the original PR

Use `gh` to identify an open original PR whose head OID exactly equals the
resolved target commit. Prefer a PR explicitly established earlier in the
conversation or repository context; otherwise inspect PRs associated with the
target commit and open PR heads.

- Require an exact head OID match. Tree equality alone is not sufficient.
- If exactly one open PR matches, use it.
- If multiple PRs match, present them and ask the user to choose.
- If none match, stop publication and explain how the user can identify the
  original PR. Do not guess from branch names alone.
- Recheck the selected PR immediately before mutation. If its head moved away
  from the resolved target, stop publication.
- Record its number, URL, title, head repository, head branch, and head OID.

The draft dissection PR targets the original PR's head/source branch, not the
original PR's base branch and not the repository default branch. This makes it
a review aid stacked on the implementation branch rather than a competing
implementation PR. If the original head repository is missing or inaccessible,
stop publication.

### Resolve the push destination

Select an existing writable remote in the same GitHub repository network from
which a PR can be opened against the original PR's head repository. Do not add
or rewrite remotes. Do not assume `origin` is correct when the original PR uses
a fork. If no destination is unambiguous, show the candidates and ask the user.

Inspect `refs/heads/dissect/<run>/result` on that remote:

- if absent, plan a new push;
- if it equals the local result OID, plan no push;
- if it is an ancestor of the local result, plan an ordinary fast-forward push;
- if it is ahead or diverged, stop rather than force-pushing.

Search all PR states in the original head repository for a PR using this result
branch. Search the original PR's comments for an existing dissection link.

### Idempotency markers

Put a stable hidden identity marker in the draft PR body:

```html
<!-- opencode-dissect:v1 original=OWNER/REPO#NUMBER target=TARGET_SHA tree=TREE_SHA run=RUN -->
```

Put a corresponding marker containing the dissection PR number in the original
PR comment. On rerun:

- reuse an open draft PR only when its marker, head branch, head OID, base
  branch, target SHA, and tree SHA all match;
- skip a push when the remote result already equals the local result;
- skip an original-PR comment when its marker and URL already match;
- stop before overwriting an unrelated PR or comment that happens to use the
  same branch or URL;
- stop and ask before reopening a closed PR, converting a ready PR back to
  draft, or replacing user-edited content;
- preserve user-authored PR body text outside clearly marked generated content.

### Final publication confirmation

After preflight, present one concise summary containing:

- original PR URL and exact target snapshot;
- local result branch, commit OID, and equivalent tree OID;
- push remote URL and whether the push is new, fast-forward, or unnecessary;
- draft PR repository;
- draft PR base: the original PR's head branch;
- draft PR head: the pushed result branch;
- whether a draft PR or original-PR comment will be created or reused.

Ask a yes/no question: "Publish exactly this dissection now?" Do not mutate any
remote state without an affirmative answer to this second confirmation.

### Publish

Push only the result branch, bypassing hooks but never forcing:

```text
git push --no-verify <remote> \
  refs/heads/dissect/<run>/result:refs/heads/dissect/<run>/result
```

Create the draft PR in the original PR's head repository with its head branch as
the base. Use a clear title such as `[Dissection] <original PR title>`. Lead the
body with this warning:

> This is an alternate review structure for the original PR. It is not an
> implementation PR and must not be merged.

Populate the body with:

- the original PR link and exact target snapshot;
- the resolved base and target;
- both identical tree IDs and the empty binary-diff result;
- the reconstructed numbered `git log --graph` output;
- piece explanations and prerequisites;
- the suggested substantive review order;
- an explicit note to stop before trailing `imports`, `tests`, and `cruft`;
- the Tig command for the local review.

Comment on the original PR with the draft dissection PR URL, target snapshot,
and tree ID. State that it provides an alternate review structure with an
equivalent final tree, is not an implementation PR, and must not be merged.

### Verify publication

Verify all of the following from remote data:

- the remote result ref equals the local result OID;
- the new PR head repository, branch, and OID are correct;
- its base is the original PR's head branch;
- it is still a draft and its URL is known;
- its body contains the identity marker and equivalence proof;
- the original PR contains exactly one matching link comment.

Recheck the original PR head. If it moved during publication, report that the
dissection proves equivalence only to the recorded snapshot. Do not rewrite the
claim or force-update anything automatically.

Failures are resumable. If pushing succeeds but PR creation fails, preserve the
remote branch. If PR creation succeeds but commenting fails, preserve the PR.
If comment verification fails, search by marker before retrying. Never roll back
by deleting a remote branch, PR, or comment; report the partial state so a rerun
can continue idempotently.

## Phase 7: Report

Report:

- the resolved base, target, and target tree ID;
- the final graph, generated from the resulting Git history with
  `git log --graph --oneline --decorate --topo-order <base>..<result>`, with one
  commit per row and topology lines on the left;
- each piece's reviewer-facing explanation and prerequisites;
- the scope placed in the trailing `imports`, `tests`, and `cruft` commits;
- the result branch and its tree ID;
- whether exact tree equality was proven;
- how many reviewer-simulation passes were performed and what they refined;
- whether commit numbering was verified against the final result history;
- publication status, including the draft PR and original-comment URLs when
  publication was requested;
- any correction commits, unresolved concerns, or intentionally imperfect
  boundaries;
- confirmation that the original worktree was left unchanged.

Do not supplement or replace the final graph with an abstract node-and-arrow
diagram. End with a suggested review order that stops before the trailing
`imports`, `tests`, and `cruft` commits.

The final item in the response must be a copy-pastable Tig command that shows
only commits reachable from the dissection result and not from its base. Use the
resolved base commit and actual result branch name:

```text
tig <base>..dissect/<run>/result
```

Put this command in a fenced code block and output no text after it.
