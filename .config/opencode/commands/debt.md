---
description: Review project for tech debt, categorized by type
---

# Tech Debt Review

**Input:** $ARGUMENTS

Review the project for technical debt across defined categories. Identify, classify, and present findings grouped by debt type. Offer to create tickets or export a report.

## Phase 1: Scope Determination

1. **Parse input:**
   - If arguments name a specific debt type (matching a built-in or project-specific type), enter **focused mode** for that type only.
   - If arguments specify a directory or file pattern (e.g., `src/api/`, `**/*.ts`), constrain the analysis scope to those paths.
   - Both can combine (e.g., `error-handling src/api/`).
   - If no arguments are provided, proceed with full-project, all-types analysis.

2. **Assess project scale:**
   - Get a rough sense of the project's size: file count, number of top-level modules/directories, language diversity.
   - If the project is small and the debt type set is nominal, proceed directly without confirmation.
   - If the project is large enough that a full analysis across all types will take significant time, present the user with a brief summary of the scope ("This is a large project with N files across M modules. A full scan across all 12+ debt types will take a while.") and offer the **advanced mode**:
     - Select specific directories or modules to analyze
     - Select specific debt types to include or exclude
     - Choose thoroughness level (quick survey vs. deep audit)
   - If the user provides enough information through their arguments that the scope is already clear, skip the advanced mode prompt and proceed.

3. **Confirm scope:**
   - State the resolved scope: which types, which paths, what thoroughness.
   - If the expected workload is significant, ask the user to confirm before launching analysis.
   - If modest, proceed without asking.

## Phase 2: Context Gathering

Launch a **subagent** to collect project context. This must complete before any analysis begins.

The subagent should collect and return:

- **Language(s) and framework(s)** in use
- **Project structure overview** — key directories, modules, entry points, and their purposes
- **Coding conventions** — linter configs (`.eslintrc`, `pyproject.toml [tool.ruff]`, etc.), `.editorconfig`, style guides, `CONTRIBUTING.md`, any documents describing preferred practices
- **Architectural guidance** — ADRs, architecture docs, README sections describing design intent, module boundary conventions
- **The current HEAD commit SHA** — record this now; all commit-pinned links will use this SHA
- **Project-specific debt types file** — check for a project-specific debt types file and include its contents if found (see Deferred Considerations for file format/location — for now, check for `.opencode/debt-types.md`, `DEBT_TYPES.md`, and `.debt-types.md` in the project root)

The subagent returns a structured context summary that will be distributed to all analysis subagents.

## Phase 3: Analysis

### Built-in Debt Types

Each type includes a name and a description of what to look for. These are guidance, not rigid search procedures — apply judgment in the context of the specific project.

**1. TODO/FIXME/HACK markers**
Acknowledged debt left by developers. Search for `TODO`, `FIXME`, `HACK`, `XXX`, `TEMP`, `WORKAROUND`, and project-specific variants. Use git blame to assess age and staleness. Consider location — markers in critical paths matter more than in utilities.

**2. Dead code**
Unused imports, unreferenced functions/classes/variables, unreachable branches, commented-out code blocks. Distinguish genuinely dead code from code that's reachable through dynamic dispatch, reflection, or external entry points.

**3. Code duplication**
Repeated logic that should be abstracted. Copy-pasted blocks, near-identical functions with minor variations. Focus on production code — duplicated test setup may be intentional for isolation.

**4. Complexity hotspots**
Overly long functions, deeply nested conditionals, functions with too many responsibilities. The code "everyone is afraid to touch." Look for functions that would benefit from decomposition.

**5. Hardcoded values**
Magic numbers, embedded strings, URLs, timeouts, limits, and configuration that should be externalized or named as constants. Distinguish deliberate defaults from values that should be configurable.

**6. Inconsistent error handling**
Mixed error handling patterns within the same codebase — exceptions vs. return codes vs. silent failure. Swallowed errors, missing error handling on operations that can fail, inconsistent error propagation.

**7. Missing or inadequate tests**
Untested critical paths, skipped/disabled tests, tests that assert nothing meaningful, tests that are brittle or tautological. Focus on gaps in coverage of important logic rather than raw coverage numbers.

**8. API/interface inconsistencies**
Naming convention mismatches across similar interfaces, inconsistent parameter ordering, return type inconsistencies, functions that do similar things but have different signatures without justification.

**9. Dependency issues**
Outdated dependencies with known issues, unnecessary dependencies that could be removed, duplicated functionality pulled from multiple packages, dependencies that have been abandoned or deprecated.

**10. Missing type safety**
Untyped code in typed languages, liberal use of `any`/`Object`/`void*`, missing null checks, type assertions used to paper over design issues. Evaluate against the project's own type strictness conventions.

**11. Documentation debt**
Missing or outdated documentation, undocumented public APIs, stale README sections, misleading comments that describe what the code used to do rather than what it does now.

**12. Logging/observability debt**
Missing logging on error paths, inconsistent log levels, no structured logging where it would be valuable, missing metrics or tracing in critical flows. Evaluate against the project's observability practices.

### General Analysis Guidance

These principles apply to all analysis subagents:

- **Context first.** Understand the project's conventions and intentional patterns before judging. A pattern that looks like debt in isolation may be a deliberate choice in context.
- **Genuine debt vs. intentional design.** Evaluate whether each finding represents actual debt or a conscious trade-off. Note your confidence level. A `# type: ignore` with a comment explaining why is different from a bare `# type: ignore`.
- **Prefer precision over recall.** It is better to omit a borderline finding than to include noise. When uncertain, note it as a possible finding with lower confidence rather than stating it definitively.
- **Per-finding data:** For each finding, record:
  - File path and line number
  - Brief description of the issue
  - Why it constitutes debt (the rationale)
  - Coarse severity: low / medium / high
  - Estimated fix effort: trivial / moderate / significant
- **Per-group data:** For the debt type as a whole, assess:
  - Overall severity
  - Scope — how widespread, whether concentrated or scattered
  - Impact type — maintenance burden, reliability risk, onboarding friction, performance risk, security risk, etc.
  - Impact level — low / medium / high

### Subagent Dispatch

- For each debt type that is in scope, launch a dedicated **subagent**.
- Each subagent receives:
  - The context summary from Phase 2
  - The type definition (from the built-in list above or the project-specific file)
  - The general analysis guidance
  - The scope constraints (paths, thoroughness) from Phase 1
- **Run subagents in parallel** — they are independent of each other.
- Each subagent returns:
  - A prose summary of what was found for this type (a few sentences to a short paragraph — what patterns were observed, where they concentrate, what the likely causes are)
  - The list of findings with all per-finding data
  - The per-group severity/scope/impact assessment
- If a subagent fails, report which type failed, continue with the others, and note the incomplete analysis in the final output.

## Phase 4: Presentation

Collect results from all analysis subagents and assemble the output.

### Output Structure

Present the results in this order:

1. **Per-type prose summaries** — for each debt type that produced findings, display its prose summary from the analysis subagent. These provide the narrative context: what patterns were found, where they're concentrated, how severe they are, and what the likely cause is. Types with no findings are omitted from this section.

2. **Brief note on clean categories** — a single line noting how many categories had no findings (e.g., "No findings for 7 other categories: ...").

3. **Executive summary table** — a compact table at the bottom, right above the prompt. This is what the user sees first without scrolling. Columns: debt type, finding count, severity, effort. Only types with findings are included.

The executive summary table must be the **last thing printed** so it is always visible above the prompt.

## Phase 5: Discussion and Refinement

After presenting findings, open a discussion with the user.

- The user may ask for **detailed findings** on any category. When they do, provide the rich drill-down: file:line, description, severity, effort, and rationale for each finding. Do not provide only a terse list — include the "why it's debt" reasoning.
- The user may **challenge findings** as false positives. Remove challenged items from the findings for that group. Adjust the group's overall assessment if the removals change the picture.
- The user may **reclassify** severity or effort on individual findings or groups.
- The user may ask questions about any finding or category — answer based on the analysis context.
- The user may ask to **re-analyze** a specific type with different guidance.

Continue the discussion until the user indicates they are ready to proceed.

## Phase 6: Action

When the user is ready, present the options:

1. **Create tickets** — for selected categories
2. **Export markdown report** — save findings to a local file
3. **Both**
4. **Neither** — end the session

Ask: "Which categories would you like to create tickets for?" with options: all / select by name or number / none.

### Ticket Creation

**Determine destination:**
- Check if `gh` is available and a GitHub remote exists. If so, default to GitHub Issues.
- Look for project hints (`.github/` directory, issue templates, `CONTRIBUTING.md` mentioning where to file issues) to confirm conventions.
- If the destination is ambiguous, ask the user.

**For each selected category, create a ticket:**

- **Title:** `<debt type name>: <brief synthesized severity/scope summary> (YYYY-MM-DD)`
  - The date is the date of the analysis.
  - The brief summary is generated from the per-group assessment (e.g., "moderate severity, concentrated in API layer" or "43 items, mostly low severity, oldest from 2019").

- **Body structure:**
  1. **Overview** — general explanation of this type of debt and why it matters (not project-specific, educational context)
  2. **Scope** — how much of this debt was found, where it's concentrated
  3. **Impact** — what type of impact it has and at what level (e.g., "High maintenance burden — inconsistent patterns make onboarding difficult and changes error-prone")
  4. **Detailed findings** — every instance found, each with:
     - A GitHub permalink using the HEAD SHA recorded in Phase 2: `https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{line}` with link text `{path}#L{line}`
     - Brief description of the issue
     - Coarse severity tag (low / medium / high)
  5. **Suggested approach** — general guidance on how to address this category of debt

- **Create using:** `gh issue create --title "<title>" --body "<body>"`

- Report created ticket URLs to the user as they are created.

### Markdown Report Export

- Default filename: `debt-report-YYYY-MM-DD.md` in the project root.
- If the user wants a different name or location, accommodate.
- The report contains the same structure as the terminal output: per-type prose summaries, detailed findings with commit-pinned links, and the executive summary table.

## Error Handling

These principles apply across all phases:

- **Transient errors** (HTTP 5xx, 429 rate limits, network timeouts): retry up to 3 times with a brief pause between attempts before reporting the failure to the user.
- **Authentication/permission errors** (401, 403): inform the user and stop — this likely needs manual intervention.
- **Subagent failures:** Report which debt type's analysis failed. Continue with all other types. Note the incomplete analysis in the final output and the executive summary.
- **Unexpected errors:** Show the full error output and ask the user how to proceed.

## Deferred Considerations

Items identified during design that need future attention. This section is intentionally included so that `/debt` can find its own deferred items.

### Architectural debt as a built-in type
Circular dependencies, layer violations, god classes/modules. Deferred because it is hard to define generically without knowledge of the project's intended architecture. Revisit as a potential built-in type or as a recommended project-specific type with guidance on how to define it.

### Label detection and reuse strategy
When creating tickets, should the command detect existing labels in the repository (e.g., `debt`, `cleanup`, `chore`) and reuse them, or always propose creating a `tech-debt` label? Needs investigation into common conventions and a strategy for label management.

### Project-specific debt types file
Format, location, and behavior for a project-specific file that defines additional debt types. Open questions:
- **Location:** `.opencode/debt-types.md`, `DEBT_TYPES.md`, `.debt-types.md`, or elsewhere?
- **Format:** Markdown with headings per type? YAML? Something else?
- **Interaction with built-ins:** Purely additive? Can project types override a built-in definition? Can the file suppress built-in types that aren't relevant?
- For now, the command checks a few candidate locations and includes any found file's contents as additional types. The formal specification of this file is deferred.
