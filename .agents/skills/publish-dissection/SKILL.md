---
name: publish-dissection
description: Publish an existing, verified Git dissection as an alternate-review draft PR and link it from the original PR. Use for that separate review aid, not for replacing an implementation PR's branch.
---

# Publish a Dissection

Publish an already reconstructed result; do not redesign or rebuild its history.
Use this workflow when the user requests an alternate-review draft PR. Updating
an existing implementation PR is a different publication outcome.

## Required reconstruction context

Read the original target OID, resolved base, result branch and OID, equivalent
tree OID, numbered graph, category scopes, review order, and run name from the
completed reconstruction. Obtain missing values from Git and context; ask only
when the selection is ambiguous. Read [dissect](../dissect/SKILL.md)
if reconstruction is incomplete rather than inventing a publication snapshot.

Before mutation, verify the result is still the recorded commit, its tree exactly
matches the recorded original target, and its commit count and numbering match
the reconstruction. Require the completed review of actual commit diffs. The
result must use a distinct head branch from the original PR.

Perform read-only preflight first. Publication authorization covers only the
actions the user requested; complete the PR and comment drafts before asking
for any authorization still needed. Do not publish merely because `dissect`
or `trisect` was invoked.

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

Inspect `refs/heads/<result-branch>` on that remote:

- if absent, plan a new push;
- if it equals the local result OID, plan no push;
- if it is an ancestor of the local result, plan an ordinary fast-forward push;
- if it is ahead or diverged, stop rather than force-pushing.

Search all PR states in the original head repository for a PR using this result
branch. Search the original PR's comments for an existing dissection link.

### Idempotency markers

Keep the legacy `opencode-dissect` marker names so previous dissections remain
discoverable across hosts and reruns do not create duplicate PRs or comments.
They identify the artifact format, not the host executing the skill.

Put a stable hidden identity marker in the draft PR body:

```html
<!-- opencode-dissect:v1 original=OWNER/REPO#NUMBER target=TARGET_SHA tree=TREE_SHA run=RUN -->
```

Put a corresponding marker containing the dissection PR number and first review
commit SHA in the original PR comment:

```html
<!-- opencode-dissect-link:v1 original=OWNER/REPO#NUMBER dissection=OWNER/REPO#NUMBER first=FIRST_SHA target=TARGET_SHA tree=TREE_SHA run=RUN -->
```

On rerun:

- reuse an open draft PR only when its marker, head branch, head OID, base
  branch, target SHA, and tree SHA all match;
- skip a push when the remote result already equals the local result;
- skip an original-PR comment when its marker and direct first-commit review URL
  already match;
- stop before overwriting an unrelated PR or comment that happens to use the
  same branch or URL;
- stop and ask before reopening a closed PR, converting a ready PR back to
  draft, or replacing user-edited content;
- preserve user-authored PR body text outside clearly marked generated content.

### Review the publication plan

After preflight, present one concise summary containing:

- original PR URL and exact target snapshot;
- local result branch, commit OID, equivalent tree OID, and the draft PR/comment text;
- push remote URL and whether the push is new, fast-forward, or unnecessary;
- draft PR repository;
- draft PR base: the original PR's head branch;
- draft PR head: the pushed result branch;
- first commit SHA in final topological order and, when reusing a draft PR, its
  direct review URL;
- whether a draft PR or original-PR comment will be created or reused.

Apply existing explicit authorization to the concrete actions described above.
If authorization is still needed, ask: "Publish exactly this dissection now?"
Do not repeat an approval already supplied. Complete the reviewable preflight
and text before asking.

### Publish

Push only the result branch, bypassing hooks but never forcing:

```text
git push --no-verify <remote> \
  refs/heads/<result-branch>:refs/heads/<result-branch>
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
- the selected category scopes and where the substantive review ends;
- the Tig command for the local review.

After creating or identifying the draft PR, resolve the first review commit from
the final numbered history:

```text
git rev-list --reverse --topo-order <base>..<result> | sed -n '1p'
```

Construct its GitHub commit-review URL as
`<draft-dissection-pr-url>/changes/<first-commit-sha>`. Comment on the original
PR with a compact human-readable link such as
``[`<first-short-sha>` (#<dissection-pr-number>)](<direct-review-url>)``. Use the
direct first-commit review URL rather than the draft PR's overview URL, and
include the target snapshot and tree ID. State that it provides an alternate
review structure with an equivalent final tree, is not an implementation PR,
and must not be merged. Include the complete corresponding idempotency marker
with the original PR, dissection PR, first full commit SHA, target SHA, tree SHA,
and run name.

### Verify publication

Verify all of the following from remote data:

- the remote result ref equals the local result OID;
- the new PR head repository, branch, and OID are correct;
- its base is the original PR's head branch;
- it is still a draft and its URL is known;
- its body contains the identity marker and equivalence proof;
- the direct review URL names the first commit from the verified final
  topological order;
- the original PR contains exactly one matching direct first-commit link
  comment.

Recheck the original PR head. If it moved during publication, report that the
dissection proves equivalence only to the recorded snapshot. Do not rewrite the
claim or force-update anything automatically.

Failures are resumable. If pushing succeeds but PR creation fails, preserve the
remote branch. If PR creation succeeds but commenting fails, preserve the PR.
If comment verification fails, search by marker before retrying. Never roll back
by deleting a remote branch, PR, or comment; report the partial state so a rerun
can continue idempotently.
## Report

Report the draft PR URL, direct first-commit review URL, original-PR comment URL,
and verified remote result OID. Identify any partial publication state clearly.
