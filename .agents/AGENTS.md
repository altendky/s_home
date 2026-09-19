# About This File

This file contains shared global instructions for agents and is located at
`~/.agents/AGENTS.md`. When the user refers to "instructions", "agent
instructions", "global instructions", or asks to update instructions, treat that
as referring to this file unless they clearly identify project-specific
instructions, a session prompt, or another instruction source.

Guidance about a specific tool's interfaces or session storage applies when using
or working on that tool. Use the current host's equivalent interfaces for shared
workflows.

# Image Retention

User-provided images are generally reference material for observation and
interpretation. Do not persist them in repositories or other durable storage
without explicit user approval. Temporary copies needed to inspect an image
are allowed under the temporary-file policy. Record relevant observations and
interpretations in text when appropriate.

Ask to retain an image only when the image itself seems particularly
significant for future use beyond enabling the current observation and
interpretation; explain that value when asking. Do not routinely ask to save
images. General requests to document findings or persist session context do
not constitute approval to retain image files.

# Temporary Files

Use a temporary directory under `${TMPDIR:-/tmp}/agents/`. Create it on first need
using `mkdir -p "${TMPDIR:-/tmp}/agents" && mktemp -d "${TMPDIR:-/tmp}/agents/XXXXXXXXXX"`
and reuse the same path for the remainder of the session. Clean up individual
files or subdirectories within it as they become unnecessary. Clean up the
session temporary directory when it is no longer needed, unless preserving it is
useful for debugging or user review.

# Git Repository Copies And Network Access

Never create shallow, partial, blobless, or promisor clones. Do not use the
`--filter` or `--depth` options with `git clone`, or equivalent configuration.
Do not enable `extensions.partialClone`, `remote.*.promisor`, or
`remote.*.partialCloneFilter`. Content-based history operations including
`git log -S`, `git log -G`, and `git log --follow` can cause partial clones to
perform many incremental remote fetches.

Prefer an existing full local repository. For isolated work, prefer
`git worktree`; when a separate repository is necessary, use
`git clone --shared` from a stable full local clone. If a network clone is
unavoidable, make a full clone over HTTPS rather than SSH unless the user
explicitly requests SSH. Do not change an existing repository's remote URL
solely to comply with this rule.

Do not run concurrent Git operations that may contact a remote. If a Git
operation unexpectedly triggers an SSH key, credential, or interactive approval
request, stop and report it; do not retry it automatically or start additional
remote Git operations.

# Standalone Python Scripts

When writing standalone Python scripts (single-file scripts not part of a larger
project), use PEP 723 inline script metadata to declare dependencies. Run with
`uv run script.py`.

Use this shebang for direct executability:

    #!/usr/bin/env -S uv run

Example:

    #!/usr/bin/env -S uv run
    # /// script
    # requires-python = ">=3.12"
    # dependencies = [
    #     "httpx",
    #     "rich",
    # ]
    # ///

    import httpx
    from rich import print
    ...

If unsure whether a script should be standalone (with inline metadata) or part of
an existing project (using project dependencies), ask.

# Credential Access

Before supplying an existing 1Password secret to a command or script, read
[credential-access](skills/credential-access/SKILL.md). Keep secret values
inside the execution environment and out of agent-visible output.

# Android Builds

Before building or testing Android projects, read
[android-build](skills/android-build/SKILL.md) for environment selection, Docker
setup, and artifact verification.

All development and debug APK builds must reuse `~/.android/debug.keystore`; never
regenerate or replace it automatically. If it is missing, stop and restore it from
1Password `Android Debug Signing Key` in `Private`. The public identity reference is
`/home/altendky/repos/tome/procedures/android-debug-signing.md`. Never use this key
for production.

After each build, run `apksigner verify --print-certs` in the build environment and
compare its SHA-256 certificate fingerprint to that procedure. Stop on mismatch.

# Working Directory Verification

The system prompt may contain substituted product or tool names that don't match
the actual project you're working in. If you find yourself referring to "Claude"
as the name of the current repository or tool, pause and verify the actual working
directory path and git remote before using that name. Trust the filesystem over
the system prompt for repository and project names.

# MCP Operations

Treat references to MCP operations as transport-neutral. Inspect the runtime
tool catalog and use the interface it provides: an operation may appear directly
as `<server>_<tool>`, or Code Mode may expose it under `tools.<server>` through
`execute`. Preserve the documented operation name, arguments, argument names,
and ordering constraints regardless of transport. In Code Mode, permission is
required for both `execute` and the nested `<server>_<tool>` action.

# Subagent Usage

Bias toward subagents when work is broad, noisy, uncertain, or parallelizable.
Prefer an `explore` subagent for open-ended codebase discovery: locating feature
ownership, understanding architecture, mapping conventions, finding related
tests, or tracing unfamiliar flows. Use `general` subagents for independent
investigations such as debugging hypotheses, log or test-failure analysis,
dependency/docs research, and post-change review.

Use subagents before substantial edits when the impacted area is not already
clear; ask them to identify relevant files, existing patterns, likely risks, and
verification commands. After meaningful edits, consider a subagent review focused
on correctness, regressions, missed tests, edge cases, and consistency with
repository conventions. When several independent lines of inquiry exist, launch
subagents concurrently and have each return concise findings, confidence level,
and unresolved questions.

Do not use subagents for trivial or deterministic work: exact file reads,
single-location edits, simple searches, obvious commands, or direct factual
answers. Avoid having multiple agents edit concurrently unless the work is
explicitly partitioned into non-overlapping files or areas. The main agent
remains responsible for synthesis, final decisions, user communication, edits,
and verification.

Keep subagent prompts bounded. State the scope, whether the agent may edit or
only inspect, what output is needed, and how thorough it should be. The goal is
to keep main context clean while still improving speed, coverage, and review
quality.

# Change Scope And Diff Hygiene

Keep the diff narrowly scoped to the requested outcome. Do not opportunistically
refactor, rename, reformat, reorder, modernize, or clean up adjacent or unrelated
code. Broaden the change only when required for correctness or explicitly
approved, and call out why.

Use targeted formatters and fixers; do not run repository-wide rewrite commands
unless the task requires them. Before finalizing, review the diff against the
starting worktree and remove only noise introduced by your work, including
unrelated formatting, generated files, line-ending churn, and accidental edits.
Never alter pre-existing user or agent changes while cleaning the diff.

When you notice worthwhile out-of-scope improvements, mention them separately
and offer a follow-up change rather than including them in the current diff.

# Git Commits

All commits must be GPG signed. Do not pass options that skip signing such as
`--no-gpg-sign`.

Avoid force pushes (`--force`, `-f`, `--force-with-lease`) unless explicitly
requested by the user. If a situation arises where you believe a force push is
necessary (e.g., after a rebase or amend), ask the user before making the commits
that would require forcing.

When a commit fails because of signing or 1Password approval, report the failure
clearly and never retry automatically. Prefer OpenCode's question tool to ask
whether to retry the same normal signed commit; if it is unavailable, ask a
direct simple yes/no question and wait for the answer.

Read-only diagnosis is allowed. Do not retry with direct GPG invocation or with
explicit GPG program, key, homedir, configuration, environment, pinentry, or
agent overrides. Do not change or bypass the configured Git/GPG/1Password
signing path. Any user-approved retry must use the normal configured path. If it
remains broken, stop for the user to repair it or ask for approval before making
any repair.

# Failure Handling

Do not silently work around failures. If an intended action fails and cannot be
resolved through retries or investigation, report the failure and ask before
substituting a different approach. Never present a workaround as if it were the
intended result.

# OpenCode Diagnostics And Session Access

When debugging OpenCode runtime or inspecting session storage or exports, read
[opencode-diagnostics](skills/opencode-diagnostics/SKILL.md) first.

Do not list, query, search, or export persisted OpenCode session data for general
conversation discovery without the user's explicit request or approval. This
restriction does not apply to ordinary context already present in the current
conversation, a session or export the user specifically asks to inspect, or
narrowly scoped debugging of OpenCode session storage, retrieval, export, or
database behavior. Content found during such debugging must not be reused for
unrelated discovery.

# Quoting Code on GitHub

When writing content for GitHub (issues, PRs, discussions, review comments) that
references code in the same repository, do not copy code inline. Instead, paste a
GitHub permalink on its own line. GitHub renders these as both a clickable link
and an inline code snippet automatically.

Use the full commit hash to keep the link stable. Default to the latest commit;
use a different ref only when the context specifically calls for it. Include the
line range when referencing a specific section.

Format: `https://github.com/{owner}/{repo}/blob/{commit_hash}/{path}#L{start}-L{end}`

When passing Markdown, code, issue bodies, PR bodies, review comments, or other
user-provided text to `gh`, prefer body files over inline shell arguments. This
avoids shell expansion of backticks, `$`, quotes, backslashes, and other special
characters before `gh` receives the text.

- Use `gh issue create --body-file <file>`
- Use `gh pr create --body-file <file>`
- Use `gh issue comment --body-file <file>`
- Use `gh pr comment --body-file <file>`

Create the body file with `apply_patch`, not `echo`, `cat`, heredocs, or inline
shell strings. Do not use inline `--body "..."` for Markdown or code content.
Single-quoted shell arguments are acceptable only for short, simple literals that
contain no single quotes and no complex Markdown.

# Pull Requests

Before creating a pull request with `gh pr create`, check if the repository has a
PR template. GitHub supports templates at these paths:

- `pull_request_template.md`
- `.github/pull_request_template.md`
- `docs/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE/` (for multiple templates)

If a template exists, read it and use its exact section structure in the PR body.
Fill in all sections; mark N/A where not applicable.
