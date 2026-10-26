---
name: trisect
description: "Reshape an existing Git change into three commits for human review: deletions, implementation with production documentation, and tests plus cruft. Use when asked to trisect a change or apply this three-layer review structure."
---

# Trisect

Read the user-level [dissect skill](../dissect/SKILL.md)
and use its shared analysis, reconstruction, reviewer-simulation, and equivalence
workflow with the target guidance below. Keep those shared judgments and mechanics
in `dissect` rather than duplicating them here.

Reconstruct the selected change as exactly three ordered commits. Optimize the
middle commit for a human trying to understand the change. Use the current branch
unless the user specifies another, within the authorization established for the task.

## The three layers

1. **Deletions.** Remove obsolete production code that is simply going away,
   including its attached comments. For a function whose body is entirely replaced,
   delete the old body but retain its original signature and braces. Preserve old
   code where comparing it with the replacement helps explain an incremental change.
   The usefulness of that comparison matters more than the number of changed lines.
   This commit contains deletions only; test deletions belong in the third commit.
2. **Implementation and explanation.** Include substantive additions and changes,
   caller updates, and the production comments and documentation that explain them.
   Keep production doc comments, inline explanations, reference links, README changes,
   and relevant architectural guidance here. Documentation is not cruft merely
   because it does not execute.
3. **Tests and cruft.** Include all tests, test helpers, fixtures, test configuration,
   comments and documentation for tests, import changes, and mechanical residue that
   adds little to understanding the implementation. Do not hide production behavior
   or contract changes here.

Keep examples embedded in production documentation with that documentation, rather
than separating them as tests.

Number the commits `[1/3]`, `[2/3]`, and `[3/3]`. Report the three layers and the
final-tree equivalence result briefly.
