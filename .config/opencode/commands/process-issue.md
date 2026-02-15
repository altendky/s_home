---
description: Research, assess, and address a GitHub issue
---

# Process GitHub Issue

**Issue reference (if provided):** $1

## Process

1. **Identify the issue:**
   - If no argument was provided, run `/issues` to list open issues and ask the user which to process
   - If an issue number was provided, fetch its details directly
   - If a URL was provided, fetch its details directly
   - If the argument is non-numeric, non-URL text, proceed to steps 2–3 for label-aware interpretation

2. **Gather repository labels** (only when the argument is non-numeric, non-URL text):
   - Run `gh label list --json name,description --limit 100` to retrieve all repository labels and their descriptions
   - Keep this label list as context for interpreting the argument in the next step

3. **Interpret argument with label awareness** (only when the argument is non-numeric, non-URL text):
   - Using the repository labels gathered above, consider whether the argument:
     - **Is a label name** (e.g., `next` when a `next` label exists) → filter issues by that label and present the list
     - **Semantically relates to one or more labels** (e.g., "next tickets" might relate to an `on deck` label; "urgent bugs" might relate to `priority:high` + `bug`) → filter by the inferred labels
     - **Is a directive unrelated to labels** (e.g., "pick the oldest one") → interpret as an instruction applied to the full issue list
     - **Is a mix of both** (e.g., "pick the next ticket for me") → filter by the relevant label(s) and then apply the directive to the filtered results
   - When filtering by labels:
     - Multiple labels inferred together default to AND semantics (single `gh issue list` call with multiple `--label` flags)
     - If the interpretation requires OR across labels, make separate `gh issue list --label` queries and combine/deduplicate the results
   - Present the resulting issues to the user and ask which to process, unless the argument clearly requests automatic selection of one

4. **Validate input type:**
    - If the input contains `#discussion_r` or `#r` → **stop** and inform the user: "This appears to be a PR review comment URL. Use `/process-comment` instead."
    - If the input URL contains `/pull/` → **stop** and inform the user: "This appears to be a pull request URL, not an issue. Use `/review-pr` to review PRs, or `/process-comment` for PR review comments."
    - If given a number, run `gh issue view <N> --json url --jq '.url'` and check the returned URL:
      - If the command fails (non-zero exit) → **stop** and ask the user: "Could not view issue `#N` — ensure the issue exists and you have access, or provide a full issue URL."
      - If it contains `/pull/` → **stop** and inform the user: "Number `#N` refers to a pull request, not an issue. Use `/review-pr` to review it."
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
