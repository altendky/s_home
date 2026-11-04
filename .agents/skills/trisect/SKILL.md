---
name: trisect
description: "Reshape an existing Git change into three commits for human review: unchanged moves and useful deletions, implementation with production documentation, and tests plus cruft. Use when asked to trisect a change or apply this three-layer review structure."
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

1. **Moves and useful deletions.** Prepare the comparison for the implementation
   commit. Move existing code to its intended locations before changing it, keeping
   moved bodies and attached comments unchanged. Include unchanged attached tests
   and documentation in the move; defer their substantive edits to their assigned
   layers. Mechanical module/import wiring and minimal extraction scaffolding may
   accompany the move. Moves can add lines at their destinations; this layer is
   not limited to deletions.

   Include large removals of code that goes away entirely, with its attached
   comments. Also remove an old implementation body when the differ would otherwise
   misleadingly align it with an entirely different replacement; retain the
   original signature and braces where useful. Do this only when it improves the
   second commit's comparison. Keep incremental replacements and ordinary small
   deletions with the implementation when seeing the old and new code together is
   helpful. Do not remove a body that is being moved when retaining it at the new
   location supplies the useful comparison.
2. **Implementation and explanation.** Make substantive changes against the code
   already present at its destinations. Include caller updates, configuration and
   contract changes, and production comments and documentation that explain them.
   Keep production doc comments, inline explanations, reference links, README
   changes, and relevant architectural guidance here. Documentation is not cruft
   merely because it does not execute.
3. **Tests and cruft.** Include test additions, modifications, and removals, test
   helpers, fixtures, test configuration, comments and documentation for tests,
   remaining import changes, and mechanical residue that adds little to
   understanding the implementation. Unchanged tests carried with a move belong
   in the first layer. Do not hide production behavior or contract changes here.

Keep examples embedded in production documentation with that documentation, rather
than separating them as tests.

Inspect the actual middle-commit diff: relocated code should be available for a
before/after comparison at its new location. If substantial moved code still
appears as fresh additions paired with deletions from the old location, move that
preparation into the first commit. Judge deletion boundaries by the clarity they
give this diff, not by how many removed lines can be collected in the first layer.

Number the commits `[1/3]`, `[2/3]`, and `[3/3]`. Report the three layers and the
final-tree equivalence result briefly.
