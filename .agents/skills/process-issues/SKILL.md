---
name: process-issues
description: Coordinate a scoped queue of GitHub issues through readiness assessment, implementation, PR verification, and optionally merging, including new issues discovered during analysis. Use for multiple issues or an ongoing choose-what-is-next workflow; use process-issue for a single issue.
---

# Process GitHub Issues

Draft workflow. Coordinate the queue; use [process-issue](../process-issue/SKILL.md)
for the individual issue investigation and implementation. Read that skill before
processing an item. Do not duplicate its mechanics or bypass its approval gates;
apply explicit authorization already supplied by the user. These relative links
assume installation alongside the existing user-level skills.

## Establish scope and authorization

Use the repository, issue references, labels, selection directions, and decisions
from the current conversation. Ask only for material missing information. Distinguish:

- **Queue:** explicit issues, a label-filtered set, or permission to select from
  a specified repository/backlog. A selector does not by itself authorize work.
- **Delivery boundary:** assessment only, implementation through PR, or merge
  after verification. Permission to implement does not imply permission to merge.
  Establish whether implementation authority also covers routine in-scope CI and
  review fixes; otherwise follow the applicable approval gates for those fixes.
- **Issue administration:** creating discovered issues, commenting/linking,
  changing existing issue scope, and closing invalid/duplicate issues. Do only the
  actions covered by the request; presenting findings alone is read-only.
- **Merge authority:** whether admin override is permitted. Override permission
  is not permission to ignore failed or pending required checks.
- **Continuation:** one chosen item, a finite approved set, or an explicitly
  ongoing queue. Agree a stopping boundary; do not interpret a bare "go" as
  unlimited backlog processing.

When broad implementation is authorized upfront, routine bounded plans within
that scope need not be reapproved. Still present findings and the plan before
editing. Pause for consequential product/architecture choices, material scope
expansion, or new authority. A missing answer is not approval.

## Select and assess

1. Check recent merges, open issue state, labels, linked discussions, and related
   active PRs. Do not duplicate work already implemented or being handled in
   another session. Confirm the code baseline used for the assessment.
2. Honor user priority and ordering. Otherwise choose by impact, evidence,
   readiness, dependencies, and bounded scope rather than issue number. Explain
   the recommendation briefly; distinguish a confirmed defect from proposed
   design or test debt.
3. Follow process-issue to verify the claim and plan the smallest complete fix,
   with regression coverage, verification, and unresolved decisions identified.
   Do not call an issue ready solely because its description sounds plausible.
   When the user requests assessment of an entire set, assess that set rather
   than asking them to select just one issue through the companion's picker.
4. Classify the outcome: ready; needs a decision; blocked by a prerequisite;
   needs splitting; already addressed/duplicate/invalid; or deferred. Report the
   reason. Readiness assessment does not authorize closing or editing an issue.

Default to one issue/branch/PR at a time. Independent investigations may be
delegated when permitted. Parallel implementations, dependent PR stacks, or a
combined PR need an explicit plan consistent with the user's authorization.

## Issues discovered during readiness or implementation

Analysis can uncover prerequisites, independent defects, or an oversized issue.
Do not force every finding into the current fix or discard it as out of scope.

- Verify the new claim proportionately and search existing open and closed
  issues and relevant PRs before filing. Distinguish independent reproduction,
  user-reported behavior, and an unverified hypothesis.
- Decide whether the finding is a **blocking prerequisite**, an **independent
  follow-up**, or a **split of the original scope**. Explain the dependency;
  avoid creating speculative prerequisite chains.
- With issue-creation authority, file a focused issue containing the behavior
  or gap, baseline and evidence/reproduction, bounded proposed scope, acceptance
  criteria, and relation to the original issue. Follow repository templates and
  GitHub-writing conventions. Creation authority for discovered issues covers
  these three categories unless the user restricts it. Without authority, report
  the proposed issue or split as a finding; ask before filing if filing is needed
  to continue the requested delivery. Do not turn an assessment-only task into
  an unsolicited issue-administration approval round.
- Reuse an existing issue when appropriate; adding evidence or links is also an
  external write and must be authorized. Do not silently rewrite the parent's
  scope or close it after a split.
- Filing an issue does not authorize implementing it. A prerequisite enters the
  active queue only if covered by the approved scope; otherwise request an
  expansion. Record independent follow-ups outside the active queue unless the
  user authorizes including them.
- Reorder approved work when a real dependency requires it, explaining the
  change. An independent defect should not unnecessarily block the original
  delivery. A newly discovered regression caused by the current implementation
  must be repaired before presenting that implementation as complete.

## Deliver the current item

Follow process-issue's repository-state checks. Preserve unrelated work. If the
worktree is dirty or the branch is unexpected, obtain direction unless the user
has already approved an appropriate isolation strategy. Do not stash, discard,
or carry unrelated edits into the issue commit by assumption.

Implement the approved plan, add regression coverage, run risk-appropriate
checks, and review the complete diff. Explain verification gaps and investigate
failures rather than weakening checks. Keep separate findings out of the diff
unless needed for the approved outcome.

Use configured signed commits where required, push, and create a PR linked to
the issue, following repository templates. Report the PR and actual verification
state. Do not mark the issue delivered merely because a PR exists.

Monitor checks for the current PR head and fix failures caused by the change
within scope. If existing review threads need handling, read and follow
[process-comments](../process-comments/SKILL.md), including its approach and
reply approvals. Do not infer authority to post replies or resolve threads from
permission to edit code. Do not trigger optional paid or external review services
without appropriate authorization.

Before an authorized merge, confirm the current head, required checks, review
state, mergeability, and intended base. Do not bypass substantive unresolved
feedback using admin override. If new commits or a base update require fresh
verification, wait for those checks. Report unrelated failures or access/signing
problems and request direction; follow configured failure rules without bypassing
them. After an ambiguous external-write failure, check its actual outcome before
retrying to avoid duplicate issues, comments, or merges.

## Continue and checkpoint

Verify the merge actually completed and whether the issue closed. Safely return
to the updated default branch as authorized, without disturbing other work. For
PR-only delivery, stop or proceed to the next item only according to the agreed
queue policy; an open PR is not a merged dependency.

Recheck the remaining approved queue against the new code and GitHub state.
Priorities and readiness can change. Report the completed result and the next
candidate without requesting approval already granted.

Maintain a compact checkpoint in the host's durable task/plan facility, or in an
agreed local file when cross-session persistence is needed. Do not create a
repository planning artifact or commit it without agreement. Record:

- Repository and code baseline; queue scope and delivery/stopping boundary.
- Authorization for implementation, issue administration, merge, and override.
- Completed items and issue/PR links; current issue, worktree, branch, and PR head.
- Verification results and outstanding checks/review decisions.
- Newly discovered issues, dependency reasons, and whether they entered the queue.
- Deferred items, unresolved decisions, and the next proposed action.

On resume, reconcile the checkpoint with actual repository and GitHub state;
do not repeat completed mutations or treat stale check results as current.

Stop at the agreed boundary, on an explicit user pause, or when meaningful
progress requires a decision or new authority. If one item is blocked, continue
with independent approved items by default, keeping the blocked item visible;
honor any user-required order or stop-on-blocker policy instead. This does not
authorize adding its prerequisite to the queue. If no approved item can progress,
report the decisions needed and stop. End with a self-contained summary of completed,
pending, deferred, and decision-needed work. Unchanged CI while waiting is not
itself a blocker; use the host's monitoring/wait mechanism.
