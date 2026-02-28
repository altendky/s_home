---
description: Summarize session into a continuation prompt and copy to clipboard
---
# Reincarnate

Summarize this session into a continuation prompt that can be pasted into a fresh agent session to pick up where we left off.

**Scoping (if any):** $ARGUMENTS

If scoping text is provided, focus the summary on that subset of the session's work. Otherwise, summarize the entire session.

## Phase 1: Gather Raw Material

Collect the following information before writing the prompt.

### Repository Identity

Run these commands to establish repository identity:

- `git remote -v` — remote URL(s)
- `git branch --show-current` — active branch
- `git rev-parse HEAD` — HEAD commit hash
- `git status --short` — uncommitted changes (if any, note which files)

### Session Context

Review the full conversation history (or scoped subset) and extract:

- **Objective:** What was the user trying to accomplish?
- **Key decisions:** Design choices, tradeoffs evaluated, approaches selected or rejected — and the reasoning behind them.
- **Problems & resolutions:** Bugs encountered, errors hit, workarounds applied — things the next session should not have to rediscover.
- **Constraints & preferences:** User-stated requirements, style preferences, things explicitly ruled out, libraries or patterns to use or avoid.

### Progress State

- What has been completed.
- What is in-progress or partially done.
- What remains to be done, in priority order.
- Open questions or blockers awaiting user input or investigation.

### Orientation References

- Key file paths (with line numbers where useful) that the next session will need to find quickly.

## Phase 2: Generate the Prompt

Compose a single self-contained continuation prompt using the material gathered above. Use this structure:

```
# Session Continuation

## Environment Verification
Before proceeding, verify you are in the correct environment:
- Repository: <remote URL>
- Branch: <branch>
- Expected HEAD: <short hash>
If any of these don't match, stop and confirm with the user before doing anything else.

## Objective
<what we were trying to accomplish>

## Key Decisions
<decisions made and their rationale>

## Problems & Resolutions
<issues encountered and how they were solved or worked around>

## Constraints & Preferences
<things the next session must respect>

## Current State
<what's done, what's in progress>

## Remaining Work
<what still needs to be done, in priority order>

## Open Questions
<unresolved items needing input or investigation>

## Key Files
<file paths relevant to continuation>
```

**Rules for the prompt:**

- Omit any section that has nothing to say. Do not include empty sections.
- Be concise but complete. The next session has no memory — anything important that is omitted will be lost.
- Write from the perspective of briefing a new agent, not narrating to the user.
- Do not include the ``` fences shown above — those are just to illustrate the structure.

## Phase 3: Output

**Step 1:** Print the prompt to the conversation, framed by clear bars:

```
========== REINCARNATION PROMPT ==========

<the generated prompt>

========== END REINCARNATION PROMPT ==========
```

**Step 2:** Write the prompt (just the content between the bars, not the bars themselves) to a temp file.

**Step 3:** Copy the prompt to the system clipboard. Try the following methods in order and use the first one that works:

1. `pbcopy` — if `command -v pbcopy` succeeds (macOS)
2. `wl-copy` — if `$WAYLAND_DISPLAY` is set and `command -v wl-copy` succeeds (Wayland)
3. `xclip -selection clipboard` — if `$DISPLAY` is set and `command -v xclip` succeeds (X11)
4. `xsel --clipboard --input` — if `$DISPLAY` is set and `command -v xsel` succeeds (X11 fallback)
5. `clip.exe` — if `command -v clip.exe` succeeds (WSL)
6. `tmux load-buffer -` — if `$TMUX` is set and `command -v tmux` succeeds (tmux)

**Step 4:** After the closing bar, print a status line:

- On success: `Copied to clipboard.`
- On failure: `Unable to copy to clipboard — no supported clipboard tool found. Prompt is saved to <path>.`

The status line and any other notes must come AFTER the closing bar, never between the bars.
