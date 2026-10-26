---
name: dissect
description: Reconstruct an existing Git change or patch as explanatory commits with an exactly equivalent final tree. Design a review DAG or follow a supplied layout when asked to dissect a change or rebuild its review history.
---

# Dissect Changes

Execute this workflow interactively in the current Git repository. The goal is
to reconstruct an existing change as a set of small, explanatory commits and
branches whose integrated tree is exactly the same as the original target.
The reconstruction may be a DAG: independent pieces should remain parallel,
while pieces that require earlier work should build on those prerequisite
branches. Follow a supplied review layout when the user or a specialized skill
provides one.

Prioritize review structure and explanatory value over code validation. A piece
is allowed to be an intermediate review step that does not compile, lint, or
pass tests. Exact final-tree equivalence is still required because it proves the
dissection represents the requested change; it is not a substitute for, or a
request to perform, build and test validation.

## Reuse and selected layout

A specialized skill can supply the target topology, commit categories, working
branch or isolation strategy, and reporting preferences. Those choices replace
the corresponding defaults below. A fixed layout can combine trailing categories
or keep contract mirrors in the same substantive commit; it must still make their
relationship clear and must not classify contract changes as cruft.

Keep the shared judgments here: understand the change and its contracts, choose
useful comparisons, construct the pieces, inspect their actual diffs, and prove
final-tree equivalence. Refine boundaries within the selected layout rather than
adding commits that defeat it. Do not fix bugs or change target contents during
reconstruction.

Apply scope decisions and authorization already supplied. Do not ask the user
to approve the same layout again; ask about unresolved choices that affect scope
or require authorization. Branch placement does not itself authorize replacing
history.

This workflow ends with local reconstruction and reporting. For a requested
alternate-review draft PR, use [publish-dissection](../../../.codex/skills/publish-dissection/SKILL.md).
Using reconstruction alone does not invoke that publication workflow.
This boundary does not cancel separately requested publication work. Handle an
authorized update to an existing implementation PR outside reconstruction;
do not substitute an alternate-review PR for that requested outcome.

## Input

Read the base, target, optional patch path, and review guidance from the user's
request and current conversation. Accept revisions supplied as a pair,
`<base>..<target>`, or `<default-branch>...<target>`, and a base plus a patch file
(including `<base> --patch <path>`).
Natural language is sufficient; no command template or argument substitution is
required. Treat additional text as guidance about useful boundaries, ordering,
naming, or reviewer concerns. Do not interpolate request text into shell
commands. Resolve and validate revisions and paths separately before using them.

With no base or target supplied, default to `<default-branch>...HEAD`. Detect
the default branch from the symbolic remote HEAD, preferring `upstream` and then `origin`,
and fall back to an unambiguous local `main`, `master`, or `dev`. For three-dot
input, resolve the reconstruction base with `git merge-base <left> <right>` and
use the right side as the target; this matches the tree change selected by
`git diff <left>...<right>`. Report the detected default branch and resolved
merge base before presenting the selected review structure.

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

- Before construction, verify that the current host permits shell commands,
  commits, and branch changes. If these capabilities are unavailable, complete
  permitted inspection and planning, then explain which execution capability
  is needed to construct the approved DAG.
- By default, leave the user's source branches untouched and use isolated piece
  and result branches. Follow a different selected placement only within the
  user's authorization for any history changes.
- Create every commit and merge with `--no-verify`, preserving configured commit
  signing and its normal approval path. Do not run pre-commit,
  commit-message, or merge hooks manually; they are outside the scope of review
  decomposition and can waste time or introduce unrelated failures.
- Keep construction scratch files and temporary worktrees in the shared session
  directory under `${TMPDIR:-/tmp}/agents/`, following the global temporary-file
  convention. Preserve pre-existing uncommitted work.
- For the default isolated layout, put created branches under `dissect/`.
- Before creating branches or worktrees, check for collisions with their chosen names.
  If names collide, offer to continue the prior dissection, choose another run
  name, or rebuild. Deleting or replacing prior work requires explicit approval.
- Record the original current branch, HEAD, status, and worktree list. Verify at
  completion that any changes to them are within the selected, authorized scope
  and that pre-existing uncommitted work is preserved.
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

For the default isolated layout, use these branch conventions:

```text
dissect/<run>/<piece>
dissect/<run>/result
dissect/<run>/target       # only when a patch must be materialized
```

## Phase 2: Design the Review Structure

Analyze the entire final diff before constructing commits. Group changes by
reviewable intent rather than merely by file. A useful piece should explain one
coherent idea and should be independently understandable at its point in the
graph.

Unless a different category layout was supplied, reserve these mechanical
categories instead of mixing them into the substantive review pieces:

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
review path. Production comments and documentation belong with the code they
explain, including examples embedded in that documentation. Notice test-only
items outside the main test module when assigning test changes.

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
- make each manually synchronized representation clear in its assigned substantive
  piece; in the default layout, use a dependent follow-up commit with a subject
  such as `Synchronize TypeScript wire-type mirror`;
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

When designing the topology, prefer independent root pieces when no real
dependency exists. Introduce a dependency when a piece cannot be represented or
understood sensibly without another. A supplied linear layout determines the
review sequence; do not add branches or commits that defeat it. Do not add
dependencies merely to make every intermediate piece compile or pass tests.

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

Present the proposed structure before construction. Include a topological list
and a text graph, plus the scope and rationale for each node. Format the graph
like `git log --graph`: one commit per row, topology lines on the left, and its
subject on that row. Show the categories and ordering selected for this run;
the default has `imports`, `tests`, and optional `cruft` as a linear tail.
Ask the user to approve unresolved layout choices without repeating decisions
already supplied by the request or specialized skill.

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

Create each piece in topological order. Use isolated temporary worktrees by
default; a selected workflow may use temporary indexes or another construction
method that preserves pre-existing work:

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
new evidence, and propose a revised structure. Ask before changing the selected
layout or scope, or replacing branches without existing authorization. Refinements
within the selected layout can use authorization already supplied.

## Phase 4: Integrate the DAG

For separately constructed branches, create the selected result branch from
the base (`dissect/<run>/result` by default) and merge pieces in a topological
order that respects dependencies. Do not merge both a prerequisite
and its descendant when the descendant already contains the prerequisite,
unless another leaf requires the prerequisite independently. Use
`git merge --no-verify` for every merge. A linear sequence already constructed
on its result branch needs no integration merge.

Resolve only mechanical merge conflicts whose intended result is unambiguous
from the target tree. If conflict resolution would introduce substantive code
not owned by a piece, revise the graph or the responsible piece instead of
hiding that code in the merge commit.

Give every non-trivial integration merge a Markdown commit body that tells the
reviewer which parent pieces are being combined, why they can now be considered
together, and where to continue the review. Do not use Git's default merge
message as the entire explanation.

For the default category layout, after all substantive leaves are integrated,
append the reserved changes as standalone commits in this order:

1. `imports`, containing only import changes;
2. `tests`, containing all remaining test-related changes;
3. `cruft`, when any confirmed cruft remains.

In that default layout, omit empty categories and keep the others separate,
using their category names as subjects after the numbering prefix. A specialized
layout can combine them. Do not place substantive implementation changes in
trailing mechanical commits. Create each commit with `git commit --no-verify`.

## Phase 5: Prove Equivalence and Iterate

Compare the reconstructed result with the original target in both ways:

```text
git rev-parse <result>^{tree}
git rev-parse <target>^{tree}
git diff --binary --stat <target> <result>
git diff --binary --exit-code <target> <result>
```

Success requires identical tree IDs and an empty diff. Commit IDs are expected
to differ.

If the trees differ:

1. Inspect the complete residual diff.
2. Attribute every discrepancy to the piece that conceptually owns it.
3. Update that piece and any descendants affected by the update.
4. Rebuild the result branch without force-updating or deleting prior work
   unless the user explicitly approves replacement. Preserve the selected layout;
   do not add correction commits that violate a requested fixed count.
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
- whether canonical definitions and mirrored representations are clear within
  the selected layout;
- whether dependencies are real rather than artifacts of construction;
- whether boundaries should be refined within the selected layout;
- whether the selected trailing categories contain only their assigned changes;
- whether merge commits explain their parents and advance the review narrative.

When available, ask a fresh read-only reviewer subagent to inspect the graph,
messages, and commit diffs for clarity problems. Use it as an independent
perspective, not as a replacement for the main workflow's review.

If the pass finds concrete improvements to boundaries, ordering, explanations,
dependencies, or diff readability, explain and apply refinements within the
selected layout and existing authorization. Ask before changing that layout or
scope, or replacing branches without authorization. Rebuild affected descendants
and the result, then re-prove exact tree
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

## Phase 6: Report

Follow the calling skill's reporting guidance when supplied. Otherwise report:

- the resolved base, original target and tree, and result branch and tree;
- the final graph from `git log --graph --oneline --decorate --topo-order <base>..<result>`;
- each piece's purpose and prerequisites, plus the scope of trailing categories;
- the equivalence proof, final numbering check, and reviewer-simulation findings;
- any remaining concerns and confirmation that pre-existing work was preserved.

Suggest a review order matching the selected layout. For the default layout,
stop the substantive review before `imports`, `tests`, and `cruft`. End the
standalone report with a fenced Tig command using the actual base and result:

```text
tig <base>..<result>
```

When handing off to another workflow, also retain the original target OID,
resolved base, result branch and OID, tree proof, numbered graph, review order,
category scopes, and run name. These identify the exact reconstruction; a
downstream publication step must not infer them from branch names alone.
