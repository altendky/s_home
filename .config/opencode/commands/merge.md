---
description: merge
---
# Create a Requirements and Design From Existing Changes

You are tasked with creating a set of requirements and a design from existing code changes.

**User message (if any):** $ARGUMENTS

## Process:

1. **Review the Repository State:**
  - identify the default remote branch, this is often master, main, or dev
  - identify the most recent commit present on the remote branch
  - identify the active branch
  - check for staged changes
  - check for unstaged changes
  - if the active branch has been pushed and has a pull request, identify the base branch from the remote service (GitHub, GitLab, etc)

2. **Identify the Changes to Evaluate:**
  - keep in mind the repository status already identified
  - changes to evaluate will 
  - if on the main branch then consider the staged and unstaged
  - consider the user message for any specific guidance as to what changes to evaluate

3. **Confirm Identified Changes With the User:**
  - describe the changes in multiple ways in terms of
    - inclusion of branches relative to a reference
    - commits
    - staged changes
    - unstaged changes
    - files including line ranges and total line counts
  - confirm identified changes with user
    - do not continue until they confirm
    - ask the question in a form where yes and no are sensible answers
    - address the user's questions and concerns
    - repeat this confirmation step when you think the user is ready

## Important:
- there is no explicit template to use for this task
- you are creating a brief summary for sharing with other developers
- this will often be used to create a ticket

## Remember:
- write the result from the perspective of the user
- reference existing code as is useful
- only consider inclusion of actual changes as necessary for clarity, you are not presenting the implementation
