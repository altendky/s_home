---
description: Process GitHub PR review comments
---

# Process GitHub PR Review Comments

**Input:** $1

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
     ' -f owner={owner} -f repo={repo} -F pr={pr_number}
     ```

     If `pageInfo.hasNextPage` is `true`, re-run the query with an `after: "<endCursor>"` argument on `reviewThreads` to fetch the next page. Repeat until all threads have been fetched.
   - Silently discard resolved threads (where `isResolved` is `true`)
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
   - If other unresolved threads exist, present them to the user (file path, line range, first line of comment body) and ask: "There are N other unresolved comment threads on this PR. Would you like to include any of them?"
   - Offer "all" as the first option when there are multiple threads, followed by the individual threads, and "none" to continue with only the original thread.
   - Merge selected threads into the working set alongside the original thread.

   **PR-wide mode:**
   - Present all unresolved threads (file path, line range, first line of comment body, author).
   - Default to all threads selected. Let the user confirm or deselect specific threads.

   If the working set is empty (no unresolved comments), inform the user and **stop**.

6. **Group comments:**
   - The default is **no grouping** — each thread gets its own commit. Only group threads when one of the following clearly applies:
     - **Same concrete issue in multiple places** — the comments describe the same specific change needed at multiple locations (e.g., "rename `get_val` to `get_value`" appearing in 3 files).
     - **Interleaved resolutions** — fixing one comment necessarily touches code that another comment also addresses, so they cannot be resolved independently without conflicts.
   - Do NOT group comments merely because they are in the same file, from the same reviewer, or about the same general topic.
   - If any groups are proposed, present them with a suggested primary comment per group (the most substantive or earliest).
   - Present all groups upfront before any implementation begins. For example: "Group 1: rename `get_val` → `get_value` (3 comments, primary: `src/lib.rs:42`). Group 2: add error context (1 comment, `src/api.rs:87`)."
   - Let the user adjust groupings and primary comment selections.
   - If there is only a single comment/thread total, skip the grouping presentation and proceed directly.

7. **Process each group:**

   For each group, perform the following steps sequentially. Complete one group before starting the next.

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

   **7c. Present summary and confirm approach:**
   - Summarize the feedback: a concise synthesis of what the comment thread(s) are about (e.g., "The reviewer requests that the error message include the file path for easier debugging").
   - If code changes are needed: describe the intended resolution (e.g., "I will modify the `handle_error` function in `src/lib.rs` to include `path` in the formatted error string").
   - If no code changes are needed: explain why (e.g., "This was addressed in commit `abc1234`" or "This is informational feedback that doesn't require a code change").
   - Provide the original comment URL(s) for easy access to full context.
   - **Pause and ask the user** if they would like to proceed, discuss the approach, redirect, or skip this group.
   - If no code changes are needed and the user confirms, skip to the next group (a reply will be drafted in step 9).

   **7d. Implement the fix:**
   - Make the requested changes following the comment's guidance.
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

   **9b. Present all drafts to the user:**
   - List every draft reply with its target (group, thread, file:line), marking each as primary or secondary.
   - Offer options: post all, skip individual replies (by number or reference), edit specific ones, or skip all.

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
