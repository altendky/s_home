---
description: Plan and create an issue through collaborative research and drafting
---

# Create Issue

**User input:** $ARGUMENTS

Plan and create an issue based on the user's description of intent. The process is collaborative -- research just enough to scope the issue, draft iteratively with the user, then create it.

## Principles

- Research only what is needed to write the issue. The goal is to capture intent and nominal scope, not to design the solution.
- Present findings and drafts to the user for feedback. Iterate before creating.
- Keep the issue focused on what and why, not how. Implementation details belong in the implementation, not the issue.
- When the user refines scope or adds requirements during drafting, incorporate them and re-present the full issue text so they can read the complete picture.
- Do not research implementation approaches, library choices, or solution architecture unless the user explicitly asks or has stated implementation expectations that need codebase context to capture accurately.
- When the user volunteers implementation intent, capture it faithfully but don't expand on it or research it further unless asked. Reflect the distinction between firm decisions and directional leanings.

## Phase 1: Understand the Request

1. Parse the user's input to identify the core intent, any stated constraints or preferences, and open questions that need research to answer.
2. If the request is vague, ask clarifying questions before proceeding.

## Phase 2: Search for Related Issues

Before investing in codebase research, confirm with the user then search the project's issue system for existing issues that overlap with or relate to the proposed work.

- Determine what issue system is available (Linear MCP tools, GitHub Issues via `gh`, or other available tooling)
- Search using several relevant terms (the core concept, related tooling, adjacent concerns)
- Read any issues that look potentially overlapping
- Report findings: duplicates (may want to update instead of create), related issues (should be referenced), or no overlap

## Phase 3: Targeted Research

Confirm with the user before beginning research. Investigate the codebase to fill in the specific details needed to write a well-scoped issue. Common things to look for:

- What exists today that the issue touches or depends on
- Concrete enumerations when the issue is about "all X"
- Data dependencies or preconditions
- Existing infrastructure that could be leveraged or needs to be created

## Phase 4: Draft the Issue

Write a complete issue draft and present it to the user. Structure should emerge from the content, but these are useful patterns to consider:

- **Intent** -- what should exist and why
- **Related Issues** -- references to issues found in Phase 2, with brief notes on the relationship. Place near the top so readers see connections early.
- **Scope** -- concrete enumeration of what's covered
- **Implementation Notes** -- optional, only when the user has stated implementation expectations. Brief capture of their stated intentions, not a design doc. Distinguish firm decisions from directional leanings.
- **Open questions / TBD** -- decisions explicitly deferred to implementation
- **Relevant context** -- codebase details the implementer needs to know

## Phase 5: Iterate

The user will likely refine the draft. For each round:

- Incorporate the feedback
- When changes are localized, present just the updated section
- When the user asks for the full output, or when enough has changed that the full picture is needed, re-present the entire issue text

Continue until the user is satisfied.

## Phase 6: Search Again for Related Issues

Scope may have shifted during iteration. Confirm with the user, then search the issue system again to catch anything newly relevant. Update the Related Issues section if needed.

## Phase 7: Create the Issue

Confirm with the user before creating. Determine the appropriate project/team/repository for the issue if not already established (check CLAUDE.md or similar project docs for guidance). Create via the appropriate tooling and report the issue identifier and URL to the user.
