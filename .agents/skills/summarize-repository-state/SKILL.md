---
name: summarize-repository-state
description: "Summarize the current Git repository state, including active and base branches, remote commits, staged and unstaged changes, merge base, and first-parent split point."
---

# summarize repository changes

You are tasked with creating a summary of the current repository state.

**Input:** Use the current repository and any focus or comparison instructions in the user's request.

## Process:

1. **Review the Repository State:**
  - identify the default remote branch, this is often master, main, or dev
  - identify the most recent commit present on the remote branch
  - identify the active branch
  - check for staged changes
  - check for unstaged changes
  - if the active branch has been pushed and has a pull request, identify the base branch from the remote service (GitHub, GitLab, etc)
  - the merge base of the active branch and its base
  - the split point of the active branch and its base which can be found by the first common first parent ancestor
