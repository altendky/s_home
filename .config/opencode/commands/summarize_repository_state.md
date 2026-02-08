---
description: summarize repository state
---
# summarize repository changes

You are tasked with creating a summary of the current repository state.

**User message (if any):** $ARGUMENTS

## Process:

1. **Review the Repository State:**
  - identify the default remote branch, this is often master, main, or dev
  - identify the most recent commit present on the remote branch
  - identify the active branch
  - check for staged changes
  - check for unstaged changes
  - if the active branch has been pushed and has a pull request, identify the base branch from the remote service (GitHub, GitLab, etc)
  - the merge base of the active branch and it's base
  - the split point of the active branch and it's base which can be found by the first common first parent ancestor
