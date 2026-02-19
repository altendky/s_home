---
description: Process GitHub PR review comments
---

# Process GitHub PR Review Comments

**Input:** $1

## User interaction convention

When a step calls for presenting multiple independent choices to the user simultaneously, use the **question tool** with one question per item. This allows the user to review and decide on each item independently in a tabbed interface. Each question should have a short `header` (≤30 chars), a descriptive `question` with full context, and concise option labels. The recommended option should be listed first with `"(Recommended)"` appended to its label. The user always has the option to type a custom answer.

## Process

1. **Validate and parse the input:**
   - If no input is provided, attempt to identify the PR for the current branch: `gh pr view --json number --jq '.number'`. If this succeeds, use the returned PR number → **PR-wide mode**. If this fails (no PR associated with the current branch, or not on a branch), inform the user: "No input provided and no PR found for the current branch. Provide a comment URL, PR URL, or PR number." **Stop.**
   - If the input contains `/issues/` → **stop** and inform the user: "This appears to be an issue URL, not a PR review comment. Use `/process-issue` instead."
   - If given a bare number, determine whether it refers to a PR or an issue: run `gh issue view <N> --json url --jq '.url'`. If the returned URL contains `/pull/`, treat the number as a PR number (PR-wide mode). If the command fails, inform the user and stop.
   - If given a URL like `https://github.com/owner/repo/pull/123#discussion_r1234567890` or `https://github.com/owner/repo/pull/123/files#r1234567890`, extract the comment ID (the number after `r`) → **single-comment mode**
   - If given a URL like `https://github.com/owner/repo/pull/123` (no comment fragment) or a bare number that resolved to a PR → **PR-wide mode**
   - If given just a comment ID number (and it is not a PR number), use it directly → **single-comment mode**

2. **Fetch comment data:**

   Determine the repository owner/repo from the URL or from `gh repo view --json owner,name`.

   **Single-comment mode:**
   - Fetch the linked comment: `gh api repos/{owner}/{repo}/pulls/comments/{comment_id}`
   - If the API returns 404, inform the user: "Comment not found — check the URL or ID." **Stop.**
   - Extract the PR number from the comment's `pull_request_url` field
   - Fetch all review comments for the PR: `gh api repos/{owner}/{repo}/pulls/{pull_number}/comments --paginate`
   - Build the thread for the linked comment:
     - If the linked comment has an `in_reply_to_id`, that value is the root comment's ID
     - If the linked comment has no `in_reply_to_id`, it is the root
     - Collect the root comment and all comments where `in_reply_to_id` equals the root's `id`

   **PR-wide mode:**
   - Fetch PR metadata: `gh pr view {pr_number} --json headRefName,headRefOid`
   - Fetch all review threads and their resolved status using:

      ```bash
      gh api graphql -f query='
        query($owner: String!, $repo: String!, $pr: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
              reviewThreads(first: 100) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  isResolved
                  comments(first: 100) {
                    nodes { databaseId body author { login } path line originalLine }
                  }
                }
              }
            }
          }
        }
      ' -f owner={owner} -f repo={repo} -F pr={pr_number} --jq '
        .data.repository.pullRequest.reviewThreads as $rt
        | {
            pageInfo: $rt.pageInfo,
            threads: [
              $rt.nodes | to_entries[]
              | select(.value.isResolved == false)
              | {
                  thread_index: .key,
                  num_comments: (.value.comments.nodes | length),
                  comments: .value.comments.nodes
                }
            ]
          }
      '
      ```

      The `--jq` filter discards resolved threads before output, which avoids token-bloating from long bot comments on resolved threads. Full comment bodies are preserved for unresolved threads so that structured AI agent instructions from automated reviewers (CodeRabbit, Copilot, etc.) are not lost.

      If `pageInfo.hasNextPage` is `true`, re-run the query with an `after: "<endCursor>"` argument on `reviewThreads` to fetch the next page. Repeat until all threads have been fetched.
   - Collect all unresolved threads with their comments

3. **Check thread status (single-comment mode only):**

   In PR-wide mode, resolved threads were already filtered out in step 2 — skip this step.

   - Using the GraphQL query from step 2's PR-wide mode section (or a dedicated call), check whether the target thread is resolved. Match the root comment's ID against `databaseId` to find the thread. If the root comment's ID is not found among the returned threads, paginate as described in step 2 until found or all threads are checked.
   - If `isResolved` is `true`, inform the user: "This comment thread is marked as resolved. It may have already been addressed." Ask if they want to proceed anyway or stop.
   - Check if the comment is outdated by comparing the comment's `commit_id` field (from step 2) against the PR's current head commit (`headRefOid` from `gh pr view {pr_number} --json headRefOid`). If they differ, inform the user: "This comment was made against commit `<short-sha>` but the PR head is now `<short-sha>` — the referenced code may have changed." Ask if they want to proceed.
   - If neither condition applies, continue silently.

4. **Verify branch:**
   - Get the PR's head branch: `HEAD_BRANCH=$(gh pr view "$PR_NUMBER" --json headRefName --jq '.headRefName')`
   - Get current local branch: `CURRENT_BRANCH=$(git branch --show-current)`
   - If `CURRENT_BRANCH` is empty (detached HEAD state), inform the user and **stop**.
   - If `HEAD_BRANCH` and `CURRENT_BRANCH` don't match:
     - Check for uncommitted changes: `git status --porcelain`
     - If the working copy is clean: inform the user of the mismatch and offer to check out the correct branch.
     - If the working copy is dirty: inform the user of the mismatch **and** the uncommitted changes, and offer options: stash changes and switch, or stop so they can handle it manually.

5. **Discover and select comments:**

   **Single-comment mode:**
   - Using the PR comments already fetched in step 2 and the resolved-status data from step 3, identify other unresolved comment threads on the same PR.
   - The originally-targeted thread is always included (no question for it).
   - If other unresolved threads exist, use the **question tool** with one question per additional unresolved thread:
     - `header`: `file:line` (truncated to 30 chars, e.g., `src/lib.rs:42`)
     - `question`: file path, line range, first line of comment body, author
     - `options`: `"Include (Recommended)"`, `"Skip"`
     - `multiple: false`
   - Merge all threads the user selected "Include" for into the working set alongside the original thread.
   - If only one unresolved thread exists (the original), skip the question tool entirely.

   **PR-wide mode:**
   - Use the **question tool** with one question per unresolved thread:
     - `header`: `file:line` (truncated to 30 chars)
     - `question`: file path, line range, first line of comment body, author
     - `options`: `"Include (Recommended)"`, `"Skip"`
     - `multiple: false`
   - Collect all threads the user selected "Include" for into the working set.

   If the working set is empty (no threads included), inform the user and **stop**.

6. **Group comments:**
   - The default is **no grouping** — each thread gets its own commit. Only group threads when one of the following clearly applies:
     - **Same concrete issue in multiple places** — the comments describe the same specific change needed at multiple locations (e.g., "rename `get_val` to `get_value`" appearing in 3 files).
     - **Interleaved resolutions** — fixing one comment necessarily touches code that another comment also addresses, so they cannot be resolved independently without conflicts.
   - Do NOT group comments merely because they are in the same file, from the same reviewer, or about the same general topic.
   - If there is only a single comment/thread total, skip the grouping presentation and proceed directly.
   - If any multi-thread groups are proposed, present them using the question tool in two rounds:

     **Round 1 — Group acceptance:** Use the **question tool** with one question per proposed group:
     - `header`: brief group label (e.g., `Rename get_val`)
     - `question`: which threads are in the group, why they're grouped, and the suggested primary comment
     - `options`: `"Accept"`, `"Split into separate commits"`, `"Skip entire group"`
     - `multiple: false`

     **Round 2 — Primary comment selection** (only for accepted groups that contain multiple threads): Use the **question tool** with one question per such group:
     - `header`: same group label as round 1
     - `question`: "Which thread should be the primary comment for this group?"
     - `options`: one option per thread in the group — `label`: `file:line`, `description`: first line of comment body. The agent's suggested primary should be listed first with `"(Recommended)"` appended.
     - `multiple: false`

     Skip round 2 entirely if no accepted group has multiple threads.

   - Groups the user accepted become the working groups for step 7. Groups the user chose to split become individual single-thread groups. Skipped groups are excluded from further processing.

7. **Process groups:**

   Processing is split into four phases: pre-analyze all groups, batch the approach confirmations, resolve any discussions, then implement sequentially.

   **Phase 1 — Pre-analyze all groups:**

   For each group in order, perform steps 7a and 7b:

   **7a. Understand the feedback:**
   - Read the entire thread(s) in the group to understand the full context of the discussion.
   - Pay special attention to the primary comment — it may indicate:
     - The most recent or relevant feedback to address
     - A specific decision or direction the user wants implemented
     - A follow-up request after earlier discussion
   - If a thread contains back-and-forth discussion, identify the current consensus or latest request.
   - Note the file path and line range from each root comment's `path`, `line`, and `start_line` fields.
   - Check all comments in the threads for structured prompts from automated review tools (CodeRabbit, Copilot, etc.) — these often include an "AI agent" or machine-readable instruction section. Use them as additional context.
   - **Determine whether code changes are needed.** The feedback might be:
     - A change request → proceed with implementation
     - Already addressed by a previous commit → no change needed
     - Informational, a question, or praise → no change needed
     - Something the agent or user disagrees with → no change needed (explain rationale)

   **7b. Research the context:**
   - Read the relevant file(s) mentioned in the comments.
   - Understand the surrounding code and its purpose.
   - Assess whether the feedback is valid and applicable.
   - Build the summary and intended approach for this group (to be presented in phase 2).

   **Phase 2 — Batch approach confirmation:**

   After all groups have been pre-analyzed, use the **question tool** with one question per group:
   - `header`: brief group label (e.g., `Error context`)
   - `question`: summary of the feedback, intended resolution (or explanation of why no change is needed), and original comment URL(s) for full context
   - `options`: `"Proceed (Recommended)"`, `"Skip"`, `"Discuss"`
   - `multiple: false`

   If there is only a single group, still use the question tool — the user should confirm the approach before implementation begins.

   **Phase 3 — Resolve discussions:**

   For any group the user marked "Discuss": engage in conversation with the user to clarify direction. Handle discussion groups in their original order. Once each discussion is resolved, the group becomes either "Proceed" (with an updated approach) or "Skip".

   All discussions must be resolved before any implementation begins.

   **Phase 4 — Implement sequentially:**

   For each non-skipped group, in original order, perform steps 7d through 7g. Complete one group before starting the next.

   **7d. Implement the fix:**
   - Make the requested changes following the comment's guidance and the confirmed approach.
   - Ensure changes are consistent with the codebase style and conventions.

   **7e. Verify changes:**
   - Run `git diff --name-only` and confirm only the intended files were modified. If unexpected files appear, flag them to the user.
   - Ask the user: "Would you like me to run any tests or checks before committing?"
   - If yes, run them. If failures occur, show results and let the user decide how to proceed.

   **7f. Confirm changes:**
   - Show the changes: run `git diff` to display all modifications.
   - Ask if the user is satisfied and ready to commit.
   - If no, leave the changes in the working directory for manual review or further editing. The user may ask for adjustments or choose to skip this group.

   **7g. Commit (skip if no code changes):**
   - Stage the changed files.
   - Commit with message format:

     ```text
     review comment: <brief summary>

     <description of changes made to address the feedback>

     <primary-comment-url>
     ```

   - Record the commit SHA for this group: `git rev-parse HEAD`. This will be used in steps 8 and 9.

8. **Push:**

   After all groups have been processed and committed, push once to the remote branch.

   - `REPO=$(gh repo view --json owner,name --jq '.owner.login + "/" + .name')`
   - Push to the remote branch.
   - If the push is rejected, show the error output and ask the user how to proceed (e.g., pull and retry, force push, or stop).

9. **Reply to comments:**

   After the push, draft and post replies for all groups.

   **9a. Draft all replies:**
   - For each group, build the commit URL from the SHA recorded in step 7g: `https://github.com/${REPO}/commit/${COMMIT_SHA}`
   - For each group, draft a **primary reply** for the primary comment's thread: a brief, conversational explanation of what changes were made (or why no change was needed), including a link to the commit if applicable.
   - For each group with multiple threads, draft **secondary replies** for the remaining threads: a shorter message linking to the commit. For example: "Addressed in [`abc1234`](commit-url)." (The primary reply URL will be added after the primary is posted.)

   **9b. Review and approve replies:**

   Use an iterative multi-question cycle to review and refine all draft replies:

   1. Use the **question tool** with one question per draft reply:
      - `header`: `file:line` of the target thread (truncated to 30 chars)
      - `question`: the full draft reply text, marked as primary or secondary, with target info (group, thread, file:line)
      - `options`: `"Post as-is (Recommended)"`, `"Skip"`
      - `multiple: false`
      - The user may also type a custom answer as **guidance for revision** — instructions for how to change the reply (e.g., "make it shorter", "mention the performance impact", "don't link the commit"). This is guidance, not necessarily verbatim replacement text.

   2. For any reply where the user provided revision guidance: revise the draft based on the guidance.

   3. Present **only the revised replies** in another multi-question round with the same structure (`"Post as-is (Recommended)"` / `"Skip"` + custom guidance for further revision).

   4. Repeat steps 2–3 until all remaining replies are either approved ("Post as-is") or skipped.

   **9c. Post replies in order:**
   - Post all approved **primary replies** first, each to the **root comment ID** of its thread:

     ```bash
     gh api repos/{owner}/{repo}/pulls/{pull_number}/comments \
       -f body="<primary reply text>" \
       -F in_reply_to={root_comment_id}
     ```

     Extract each primary reply's URL from the API response (`html_url` field).

   - Then post all approved **secondary replies**, updating each to include the now-available primary reply URL. For example: "Addressed in [`abc1234`](commit-url) — see [this reply](primary-reply-url) for details."

     ```bash
     gh api repos/{owner}/{repo}/pulls/{pull_number}/comments \
       -f body="<secondary reply text>" \
       -F in_reply_to={root_comment_id_of_this_thread}
     ```

   - If a primary reply was skipped but its secondary replies were approved, post the secondary replies as standalone (with commit link only, no primary reply link).
   - For any reply the user skipped, do not post it. The commits are already pushed; the user can reply manually.

## Error handling

These principles apply across all steps:

- **Transient errors** (HTTP 5xx, 429 rate limits, network timeouts): retry up to 3 times with a brief pause between attempts before reporting the failure to the user.
- **Authentication/permission errors** (401, 403): inform the user and stop — this likely needs manual intervention such as re-authentication or adjusting token scopes.
- **Not found errors** (404): inform the user with context about what was not found (comment, PR, repository) and stop.
- **Unexpected errors:** show the full error output and ask the user how to proceed.
