---
description: Compare CI workflows and settings across multiple repositories
---

# Compare Projects CI Configuration

**Repositories to analyze:** $ARGUMENTS

## Objective

Analyze and compare CI workflows, GitHub Actions settings, and related tooling configurations across the specified repositories. Identify consistency opportunities and gaps.

## Process

### Phase 1: Parallel Repository Exploration

**IMPORTANT: Maximize concurrency.** Launch parallel subagent tasks (one per repository) simultaneously to gather CI configuration details. Do NOT process repositories sequentially.

Each subagent should explore a single repository and return a comprehensive summary covering:

1. **Workflow files** (`.github/workflows/`)
   - Workflow names, structure, and patterns (reusable workflows, orchestrator)
   - CI triggers (push branches, tags, PRs, merge groups)
   - Concurrency configuration
   - Matrix strategies (OS, language versions, architectures)
   - Final status aggregation patterns

2. **Language-specific tooling**
   - Rust: `Cargo.toml` workspace lints, `rust-toolchain.toml`, `rustfmt.toml`, `.cargo/config.toml`, `deny.toml`
   - Python: `pyproject.toml`, linting/testing configuration
   - Node/TypeScript: `package.json`, build configuration
   - Other languages as applicable

3. **Pre-commit configuration** (`.pre-commit-config.yaml`)
   - All hooks enabled and their sources
   - Hook versions

4. **Tool version management**
   - `mise.toml` and `mise.lock` presence
   - Specific tool versions

5. **External service integrations**
   - `codecov.yml` configuration
   - `renovate.json5` or `renovate.json` configuration
   - `.mergify.yml` configuration

6. **Custom GitHub Actions** (`.github/actions/`)

7. **Testing configuration**
   - Test framework and runner
   - Coverage tools and configuration
   - Test output formats (JUnit, etc.)

8. **Release and publishing workflows**

The subagent prompt should instruct each to return a structured summary suitable for comparison.

### Phase 2: Comparative Analysis

After all repository exploration tasks complete, synthesize the results. This phase may also use subagent tasks to compare specific aspects in parallel if the data volume warrants it.

Compile comparison tables organized by aspect:
- Workflow architecture and patterns
- CI triggers
- Language/runtime version matrix
- OS and architecture matrix
- Pre-commit hooks (checklist showing presence across repos)
- Linting and formatting configuration
- Testing framework and configuration
- Code coverage setup
- Dependency auditing
- Tool version management
- Automated dependency updates (Renovate)
- Merge automation (Mergify)
- Custom GitHub Actions
- Release and publishing

### Phase 3: Gap Analysis and Recommendations

Identify and categorize findings:

1. **High-priority alignment opportunities**: Missing configurations that most repos have and the outlier should add
2. **Medium-priority opportunities**: Inconsistent tools or versions that could be standardized
3. **Low-priority / contextual differences**: Differences that make sense given project type, language, or deployment target

### Output

Present:
1. Comparison tables by aspect showing each repository's configuration
2. Summary of key inconsistencies
3. Prioritized list of alignment opportunities with specific recommendations

## Notes

- Repository references may be provided as GitHub URLs, `owner/repo` format, or repository names. Interpret flexibly based on context.
- Focus on actionable insights rather than exhaustive documentation.
- When configurations differ due to legitimate project differences (e.g., WASM-only vs multi-platform), note this as contextual rather than a gap.
