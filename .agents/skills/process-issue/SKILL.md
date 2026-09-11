---
name: process-issue
description: Research the validity of a GitHub issue, present findings and an implementation plan, and carry approved changes through a branch and PR. Accept an issue number or URL, label-aware selection directions, or a request to choose an open issue.
---

# Process GitHub Issue

**Inputs:** Use the issue number or URL, label names, and selection directions in the user's request and current conversation. If no issue or selection direction is supplied, list open issues for selection.

## User interaction convention

When presenting issues for selection, prefer the host's question interface for up to 15 issues only when it is available, permitted, and can represent the choices. Identify each issue by number and title and allow the user to supply a different reference or selection direction. For larger lists or unsuitable interfaces, show a concise issue list and ask a direct question in the host's permitted conversation channel.

Use an interface permitted for approval when a step needs user authorization; otherwise ask directly and wait. Apply decisions and authorization already supplied in the current conversation instead of asking the user to repeat them. A missing answer is not approval.

## Process

1. **Identify the issue:**
   - If no issue or selection direction was provided, run `gh issue list --state open` to list open issues by number and title and present them for selection following the user interaction convention above
   - If an issue number was provided, fetch its details directly
   - If a URL was provided, fetch its details directly
   - If the input is non-numeric, non-URL text, proceed to steps 2–3 for label-aware interpretation

2. **Gather repository labels** (only when the input is non-numeric, non-URL text):
   - Run `gh label list --json name,description --limit 100` to retrieve all repository labels and their descriptions
   - Keep this label list as context for interpreting the input in the next step

3. **Interpret input with label awareness** (only when the input is non-numeric, non-URL text):
   - Using the repository labels gathered above, consider whether the input:
     - **Is a label name** (e.g., `next` when a `next` label exists) → filter issues by that label and present the list
     - **Semantically relates to one or more labels** (e.g., "next tickets" might relate to an `on deck` label; "urgent bugs" might relate to `priority:high` + `bug`) → filter by the inferred labels
     - **Is a directive unrelated to labels** (e.g., "pick the oldest one") → interpret as an instruction applied to the full issue list
     - **Is a mix of both** (e.g., "pick the next ticket for me") → filter by the relevant label(s) and then apply the directive to the filtered results
   - When filtering by labels:
     - Multiple labels inferred together default to AND semantics (single `gh issue list` call with multiple `--label` flags)
     - If the interpretation requires OR across labels, make separate `gh issue list --label` queries and combine/deduplicate the results
     - Present the resulting issues for selection following the user interaction convention above, unless the input clearly requests automatic selection of one

4. **Validate input type:**
    - If the input contains `#discussion_r` or `#r` → **stop** and inform the user: "This appears to be a PR review comment URL. Use the `process-comments` skill instead."
    - If the input URL contains `/pull/` → **stop** and inform the user: "This appears to be a pull request URL, not an issue. Request a PR review, or use the `process-comments` skill for PR review comments."
    - If given a number, run `gh issue view <N> --json url --jq '.url'` and check the returned URL:
      - If the command fails (non-zero exit) → **stop** and ask the user: "Could not view issue `#N` — ensure the issue exists and you have access, or provide a full issue URL."
      - If it contains `/pull/` → **stop** and inform the user: "Number `#N` refers to a pull request, not an issue. Request a PR review instead."
      - If it contains `/issues/` → proceed

5. **Retrieve issue details:**
   - Get the full issue description, comments, and any linked context

6. **Research the claim:**
   - Investigate the validity of the issue against authoritative sources
   - Check relevant code, documentation, specs, or external references

7. **Assess validity:**
   - Determine if the issue is valid, partially valid, or invalid
   - Note any nuances (e.g., convention vs requirement)

8. **Present findings:**
   - Summarize research results
   - Provide a recommendation (fix, close, needs clarification, etc.)
   - Ask the user for their decision before proceeding

9. **Create a plan:**
   - Identify all files and locations that need changes
   - Outline specific tasks
   - Wait for user approval

10. **Check repository status:**
    - Identify the default branch (typically `main` or `master`)
    - If currently on a non-default branch, ask the user if this is intentional before proceeding
    - If there are uncommitted changes, ask the user how to proceed before continuing

11. **Execute:**
    - Switch to the default branch and pull latest changes
    - Create a new branch from the updated default branch
    - Make the changes
    - Commit with a message referencing the issue (e.g., "Closes #N")
    - Push the branch
    - Create a PR

12. **Report completion:**
    - Provide the PR URL
