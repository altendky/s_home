---
description: Generate a narrative review story from a diff (PR URL or git range)
---

# Diff Story

**Input:** $1

**Additional guidance (optional):** $2

Generate a narrative "review story" that helps reviewers quickly understand a diff. The story walks through logical sections of the change with descriptions followed by the relevant diff hunks.

## Input Handling

1. **Parse the input ($1):**
   - **GitHub PR URL** (contains `github.com` and `/pull/`): Fetch diff by appending `.diff` to the URL
   - **Git range** (e.g., `main..feature`, `HEAD~3..HEAD`): Use `git diff`
   - **Empty/missing**: Run `gh pr list --state open` and present for selection, or ask for a git range

2. **Fetch the diff:**
   - For PR URLs: `curl -sL "<url>.diff"`
   - For git ranges: `git diff $1`
   - Store the full diff content for analysis

3. **Gather context:**
   - For PR URLs: Fetch PR metadata with `gh pr view <url> --json title,body,commits,number,headRefName`
   - For git ranges: Gather commit messages with `git log --format="%s%n%n%b" $1` and determine branch name with `git rev-parse --abbrev-ref HEAD`

4. **Determine output filenames:**
   - Extract branch name and PR number (if applicable)
   - Sanitize branch name for filesystem (replace `/` with `-`, remove special chars)
   - Format: `diffstory-<branch>-<pr#>.md` and `.html` (omit `-<pr#>` if not a PR)

## Output Preferences

Before proceeding with analysis, parse the user's request (including $1, $2, and any surrounding context from the conversation) to determine which outputs they want.

**Detection rules:**
- "gist" mentioned → produce a gist
- "markdown", "md", or "local" mentioned → produce markdown file
- "html" mentioned → produce HTML file
- Multiple formats mentioned → produce those formats
- No format preference stated → ask which formats they want

**Gist visibility (determine now if gist is requested):**
- If user said "public gist" → public
- If user said "secret gist" or just "gist" → secret (default)
- If gist is requested but visibility is ambiguous → ask now: "Should the gist be public or secret (default)?"

**When only a gist is requested:**
- Generate the markdown content internally (needed for the gist)
- Do NOT write a local `.md` file
- Do NOT generate an HTML file
- Create the gist and report the URL
- The gist contains: the story markdown + `diffstory-prompt.txt`

**When only markdown is requested:**
- Write the local `.md` file
- Do NOT generate HTML
- Do NOT ask about gist

**When only HTML is requested:**
- Generate markdown internally (needed to produce HTML)
- Do NOT write a local `.md` file
- Write the local `.html` file
- Do NOT ask about gist

**When multiple formats are requested:**
- Produce exactly those formats, no more

**When no preference is stated:**
- Ask: "Which output formats would you like? Options: markdown (local file), HTML (local file), gist (GitHub), or any combination."

## Analysis Phase

For small diffs (single file, ~50 lines or fewer), skip to simplified output - produce a single-section story without the full segmentation process.

For larger diffs, use a subagent to analyze and segment the diff:

**Subagent task: Analyze and segment the diff**
- Parse the diff into per-file hunks
- Identify logical groupings (changes that belong together conceptually)
- Determine optimal reading order (not necessarily file order - order by narrative flow)
- Assign a descriptive section name to each group
- Return a segmentation plan: list of sections, each with its name and the file paths + hunk ranges it contains

The orchestration stays in the main agent. The subagent only performs the analysis.

## Narrative Generation Phase

For each section identified in the segmentation plan, use a subagent to generate the narrative:

**Subagent task: Write section narrative**
- Input: Section name, the literal diff hunks for this section, brief overall context (PR title/summary)
- Write a narrative explanation for this section:
  - What changed and why
  - How it connects to the overall change
  - Any notable implementation details or concerns
- Keep it concise - a paragraph or two, not exhaustive documentation
- Return: Section title + narrative text

Run these subagents in parallel for speed. The main agent assembles the results.

If the user provided additional guidance in $2, pass it to the narrative subagents to influence tone, focus, or emphasis.

## Assembly Phase

Combine the analysis and narratives into a single document:

```
# [Concise title describing what this change does]

## Summary
[2-3 sentences explaining the change at a high level - what and why]

---

## 1. [First Section Name]

[Narrative from subagent]

​```diff
[Literal diff hunks for this section, extracted from the original diff]
​```

---

## 2. [Second Section Name]

[Narrative...]

​```diff
[Hunks...]
​```

---

[Additional sections...]

---

## Files Changed

| File | Role |
|------|------|
| path/to/file | Brief description of its role in this change |
```

Guidelines:
- Section numbers reflect reading order, not importance
- Preserve the exact diff hunks from the original - do not modify or summarize them
- The "Files Changed" table provides a quick reference; keep descriptions brief

## Output Generation

Generate only the outputs determined in the Output Preferences section. Skip any outputs not requested.

### Markdown File (if requested)

- Save to `diffstory-<branch>[-<pr#>].md` in the current working directory
- If markdown is only needed as an intermediate for gist or HTML, keep it in memory and do not write the file

### HTML File (if requested)

- Convert the markdown to self-contained HTML
- Use inline CSS (no external dependencies)
- Style the diff blocks with appropriate colors:
  - Lines starting with `-` (but not `---`) → light red background (#ffebe9)
  - Lines starting with `+` (but not `+++`) → light green background (#e6ffec)
  - Lines starting with `@@` → light purple/blue (#f0f0ff)
  - Lines starting with `diff`, `index`, `---`, `+++` → neutral header style
- General styling:
  ```html
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #24292f; }
    h1 { border-bottom: 1px solid #d0d7de; padding-bottom: 0.5rem; }
    h2 { margin-top: 2rem; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3rem; }
    h3 { margin-top: 1.5rem; }
    hr { border: none; border-top: 1px solid #d0d7de; margin: 2rem 0; }
    pre { background: #f6f8fa; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.85em; }
    code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #d0d7de; padding: 0.5rem 1rem; text-align: left; }
    th { background: #f6f8fa; }
    .diff-remove { background-color: #ffebe9; }
    .diff-add { background-color: #e6ffec; }
    .diff-hunk { background-color: #f0f0ff; color: #6e7781; }
    .diff-header { color: #57606a; }
  </style>
  ```
- When rendering diff blocks, wrap each line in a span with the appropriate class
- Save to `diffstory-<branch>[-<pr#>].html` in the current working directory

### Gist (if requested)

- Use the visibility determined in Output Preferences (public or secret)
- Copy this command file (`~/.config/opencode/commands/diffstory.md`) to a temp location as `diffstory-prompt.txt`
- Write the story markdown to a temp file with the appropriate name
- Create gist: `gh gist create <story.md> diffstory-prompt.txt -d "<title>"`
  (add `--public` if public visibility was determined)
- Clean up temp files
- Report the gist URL

## Report Completion

Provide only what was generated:
- Paths to local files (if any were written)
- Gist URL (if created)
- A one-sentence summary of the story's main theme or finding
