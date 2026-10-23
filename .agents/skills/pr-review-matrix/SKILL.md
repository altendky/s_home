---
name: pr-review-matrix
description: Show a GitHub PR-by-reviewer matrix for PRs the user authored, was asked to review, or has reviewed. Use to monitor outgoing and incoming review requests and review decisions.
---

# PR review matrix

Produce a read-only matrix of authored PRs, incoming review requests, and PRs the
user has reviewed. Include each PR once when these scopes overlap.
Do not request reviews, post comments, or change PRs as part of this skill.

## Run the helper

Run [scripts/pr_review_matrix.py](scripts/pr_review_matrix.py) from the target
repository, using its absolute path so the working directory stays in that repo.
It is executable through `uv` and defaults to Rich-rendered terminal output. API calls use HTTPX
through AnyIO on Trio, with a shared concurrency limit and reusable connections.
Authentication uses `GH_TOKEN`/`GITHUB_TOKEN` or one local `gh auth token` lookup;
credentials stay in memory. Repository discovery reads `GH_REPO`, GitHub CLI's
local default repository, or the local origin URL. It batches PR metadata, review histories, requests,
and merge status through GraphQL, following both PR and nested review/request
pagination. Reads are fresh; the helper does not cache responses.

Defaults: authenticated GitHub user, current repository, open non-draft PRs that
the user authored, has a current individual review request for, or has submitted a
review on. Comment-only and dismissed submitted reviews count toward inclusion;
unsubmitted review drafts do not. Team requests stay separate and do not imply
an individual request to every member.
Honor the user's scope through these options:

```sh
~/.agents/skills/pr-review-matrix/scripts/pr_review_matrix.py
~/.agents/skills/pr-review-matrix/scripts/pr_review_matrix.py --repo OWNER/REPO --user LOGIN
~/.agents/skills/pr-review-matrix/scripts/pr_review_matrix.py --include-drafts
~/.agents/skills/pr-review-matrix/scripts/pr_review_matrix.py --rich
~/.agents/skills/pr-review-matrix/scripts/pr_review_matrix.py --no-rich
```

Rich-rendered terminal output is the default; `--rich` selects it explicitly.
It wraps to the terminal width and supports clickable links in supporting terminals.
Use `--no-rich` to print plain Markdown for piping. When presenting the matrix in
chat, always run the helper with `--no-rich` and render that Markdown in the response.

Use `--authored-only` for the outgoing-only view. Repeat `--repo` for multiple
repositories. Other options are `--state open|closed|all`,
`--exclude-bots`, and `--aliases PATH`. If no repo can be inferred, ask for scope.
For a more specific PR set not covered by the options, filter the retrieved rows
before computing the reviewer columns and pending totals; do not label a broader
report as the requested subset.

If the helper fails, report the failure. Do not present partial or unknown data as
blank cells. An available GitHub connector can be used when the helper cannot run,
but explain the substitution and preserve the semantics and pagination below.

## Nicknames

[reviewer-aliases.json](reviewer-aliases.json) is the user-editable mapping from
canonical GitHub login to displayed column label:

| GitHub login | Label |
| --- | --- |
| ericaltendorf | e |
| j3m7 | j |
| altendky | k |
| secemp9 | n |
| coderabbitai[bot] | 🐇 |

Use canonical logins for API lookup and matching. Unconfigured reviewers keep
their logins as labels; collisions are disambiguated with logins. Keep nickname
changes in this JSON file. The table groups people first, then bots, then teams,
and sorts by displayed label within each group.

## Cell meanings

- **🟠**: Currently requested. A re-request takes precedence over an old approval
  or change request. Missing approval alone does not imply a pending request.
- **🟥**: Changes requested, with no outstanding re-request.
- **💚**: Approved, with no outstanding re-request.
- **💬**: Submitted comments, with no outstanding request or effective approval/
  change-request decision. A comment after approval does not erase the approval.
- **Blank**: No outstanding request, active decision, or submitted comment-only
  review for that PR.

Process submitted review history chronologically. APPROVED and CHANGES_REQUESTED
replace the previous decision; COMMENTED and unsubmitted PENDING do not. DISMISSED
clears the preceding decision. If an API supplies a more precise effective state,
prefer it to reconstruction. These are reviewer states, not proof that a PR meets
all branch-protection or merge requirements.

Include bots unless excluded by the user. Exclude the author's self-comments from
reviewer discovery. Team requests have separate ORG/team columns; do not expand
them into individual requests.

## Conflicts

Prefix a PR title with **⛔** only when GitHub's GraphQL `mergeable` field is
`CONFLICTING`. `MERGEABLE` and `UNKNOWN` get no prefix; UNKNOWN is still being
calculated, not confirmation that the branch is conflict-free. Do not infer
conflicts from failed checks, requested changes, or a generic blocked state.
Missing or invalid mergeability data is an error. Include the prefix in the
legend, and keep the full title and existing reviewer/queue indicators.

## Queue column

Place a centered **Q** column at the end, after all reviewer columns.
Read GitHub's GraphQL `isInMergeQueue` and `autoMergeRequest` fields for the PRs in
scope. Show **🔶** when in the merge queue; otherwise **🟦** when auto-merge (merge
when ready) is enabled. Show blank when neither applies. Queue membership takes
precedence when both apply. Do not infer these states from passing checks,
approvals, or mergeability. Missing data or API errors must not become blank cells.
This skill only reads queue settings; it never enables auto-merge or enqueues PRs.

## Output

Return the helper's table in chat with linked PR numbers, full titles, one
centered column per reviewer, **Q** last, and pending totals. Put the
**Pending requests** label in the second column, leaving its first cell empty. Include scope, excluded draft count,
observation time, legend, and nickname key. Keep PRs without reviewers visible.
Put the user's authored PRs first, followed by other people's PRs they are reviewing.
Leave the first column's header empty and use **Authoring** as the second
column's header (above the PR titles). Insert a secondary header row with
**Reviewing** in bold in the second cell where the groups meet. Repeat the
reviewer labels and **Q** in bold in their respective columns on that row;
leave its first cell empty. If there are only reviewing rows, use **Reviewing** as the second
column's top header without a duplicate secondary header. Keep one continuous table and
descending PR order within each repository in each group. PRs qualifying for both
groups appear only in the authored group.
For multiple repos, qualify PR numbers with their repository. Escape Markdown in
titles and labels. Save or publish the report only when requested.

For helper changes, run [scripts/test_pr_review_matrix.py](scripts/test_pr_review_matrix.py)
with `uv run`, then exercise a live read-only report in the requested repository.
