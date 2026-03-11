---
description: Diagnose and repair a corrupted opencode session in the SQLite database
---

# Repair Session

**Session ID:** $ARGUMENTS

Diagnose corruption in an opencode session caused by known bugs, present findings for confirmation, then apply a targeted repair.

The opencode SQLite database is at `~/.local/share/opencode/opencode-dev.db`. The session, message, and part tables store conversation history. Parts are ordered by `time_created` within each message.

## Known Repairs

### Orphaned tool_use from missing step boundaries

**Issue:** https://github.com/anomalyco/opencode/issues/16749

**Cause:** A retryable stream error in the `finish-step` handler causes the retry to append new LLM output to the same message without persisting `step-finish`/`step-start` boundary markers. An errored step's `tool_use` merges with the successful retry's content.

**Symptom:** The Anthropic API rejects requests with either:
- `tool_use ids were found without tool_result blocks immediately after: <tool_id>`
- `Expected thinking or redacted_thinking, but found tool_use`

**Diagnosis:**

1. Find assistant messages in the session with non-null `json_extract(data, '$.error')` containing the phrase "tool_use ids were found without tool_result blocks" OR containing both "Expected" and "found tool_use"
2. Extract the orphaned tool_use ID from the error message text
3. Find the part with that `callID` — it will be a tool part with `"status":"error"` and typically `"error":"Tool execution aborted"`
4. Examine all parts in that message ordered by `time_created` — the errored step's parts (text + tool) will be followed by the retry step's parts (text + tool with `"status":"completed"`) without step-finish/step-start between them

**Repair:**

1. Delete all errored parts (text and tool from each failed attempt). The successful retry's parts are identical in purpose, so nothing is lost.
2. Delete all error assistant messages (non-null `$.error`) and any user messages that follow the last clean assistant message (they are just retry attempts after the corruption).
3. Verify: zero references to the orphaned tool_use ID remain, the repaired message has a clean step-start → content → step-finish structure, and no error messages remain.

### Empty text parts stripped from assistant messages

**Issue:** https://github.com/anomalyco/opencode/issues/16748

**Cause:** Two independent code paths strip empty text parts at API-call time (not from the DB):

1. `normalizeMessages()` in `transform.ts` filters empty text/reasoning parts from all messages, including assistant messages with thinking block signatures.
2. The AI SDK's internal `convertToLanguageModelPrompt` strips text parts where `text === ""` and `providerOptions == null`. When `message-v2.ts` sets `providerMetadata: undefined` for empty text parts with no stored metadata, the AI SDK removes them.

When empty text parts between reasoning/thinking blocks are removed, it changes the positional arrangement and invalidates cryptographic signatures in Anthropic's extended thinking blocks.

**Symptom:** The Anthropic API rejects requests with: `thinking or redacted_thinking blocks in the latest assistant message cannot be modified`

**Diagnosis:**

1. Find assistant messages in the session with non-null `json_extract(data, '$.error')` containing the phrase "cannot be modified"
2. Confirm the message immediately before the error has reasoning parts — the empty text parts between them are almost certainly still in the DB (they are only stripped at runtime, not from storage)
3. As a sanity check, verify empty text parts exist between adjacent reasoning parts. If they are genuinely missing from the DB (unlikely — would require running a now-reverted `removePart` code path), flag this for manual inspection.

**Repair:**
The DB data is almost certainly intact — the stripping happens at runtime in code that has been fixed. The repair is to delete the error messages so the session can resume with the fixed code.

1. Delete all error assistant messages (non-null `$.error` matching "thinking" or "cannot be modified") and any user messages that follow the last clean assistant message (they are just retry attempts after the error).
2. If the sanity check in diagnosis step 3 found genuinely missing empty text parts (rare), insert empty text parts (`{"type":"text","text":""}`) between adjacent reasoning blocks, with `time_created` values ordered correctly between the surrounding parts.
3. Verify: no error messages remain in the session, and reasoning parts have empty text separators between them.

**Important:** This repair only helps if the code fix from the upstream issue is applied. Without it, the same error will recur on the next turn.

### Empty text part with cache_control from aborted message

**Issue:** (no upstream issue yet)

**Cause:** When a message is aborted mid-generation (`MessageAbortedError`), the LLM may have started a text content block but produced no content before the abort. This leaves an empty text part (`"text":""`) persisted in the database within an incomplete step (no `step-finish`). On the next turn, opencode's prompt caching logic applies `cache_control` to text parts without checking whether they are empty. The Anthropic API rejects `cache_control` on empty text blocks.

**Symptom:** The Anthropic API rejects requests with: `cache_control cannot be set for empty text blocks`

**Diagnosis:**

1. Find assistant messages in the session with non-null `json_extract(data, '$.error')` containing the phrase "cache_control cannot be set for empty text blocks"
2. Identify the preceding assistant message with a `MessageAbortedError` — it will have `json_extract(data, '$.error')` containing "MessageAbortedError"
3. Confirm the aborted message has an incomplete step: a `step-start` part with no corresponding `step-finish`
4. Find the empty text part in the aborted message: a part with `json_extract(data, '$.type') = 'text'` and `json_extract(data, '$.text') = ''`

**Repair:**

1. Delete all parts belonging to the aborted message (the incomplete step's step-start, reasoning, and empty text parts).
2. Delete the aborted assistant message itself.
3. Delete all error assistant messages (non-null `$.error` matching "cache_control cannot be set for empty text blocks").
4. Keep any user messages that follow the last clean assistant message — unlike retry artifacts, these may contain genuine user input. However, if a user message is immediately followed only by an error assistant message (and no clean assistant response), it is a failed turn that should be kept so the session can resume with a response to it.
5. Verify: zero empty text parts remain in the session, the aborted message and its parts are gone, no error messages remain, and the last clean assistant message has balanced step-start/step-finish pairs.

**Caveat:** This repair unblocks the session but the underlying bug (applying `cache_control` to empty text parts) may not have an upstream fix yet. The same error can recur if another message is aborted leaving an empty text part.

## Process

1. **Parse input:**
   Extract the session ID from `$ARGUMENTS`. It will look like `ses_...`. If no session ID is provided, ask the user and wait.

2. **Diagnose:**
   Run diagnostic queries against the database to determine which repair is needed:
   1. Verify the session exists: `SELECT id, title FROM session WHERE id = '<session_id>'`
   2. Find error messages: `SELECT id, json_extract(data, '$.error') as error FROM message WHERE session_id = '<session_id>' AND json_extract(data, '$.error') IS NOT NULL ORDER BY time_created`
   3. Based on the error text, match to a known repair from the Known Repairs section above
   4. Run the repair-specific diagnosis steps to confirm the root cause and identify the exact parts/messages involved

   If the error doesn't match any known repair, tell the user what you found and stop.

3. **Report and confirm:**
   Present findings to the user:
   - Which repair was identified and a link to the upstream issue
   - The specific corrupted message and parts involved
   - What will be deleted or modified
   - Ask: "Should I proceed with this repair?"

   Wait for explicit confirmation before continuing. Do NOT proceed without it.

4. **Backup:**
   Create a backup using SQLite's built-in backup mechanism (not a file copy — this is safe even if the database is open):

   ```
   sqlite3 ~/.local/share/opencode/opencode-dev.db ".backup '/tmp/opencode-dev-backup-<session_id>-<timestamp>.db'"
   ```

   Verify the backup file exists and has nonzero size.

5. **Repair:**
   Apply the repair as described in the matched known repair entry. Run each mutation in a single sqlite3 invocation so they are atomic.

6. **Verify and report:**
   Run verification queries:
   - No error messages remain in the session
   - No references to orphaned IDs remain (for orphaned_tool_use)
   - All messages have balanced step-start/step-finish pairs
   - The session ends with a clean message (no error)

   Report to the user:
   - Which repair was applied
   - What was deleted or modified (specific part/message IDs)
   - Verification results (pass/fail for each check)
   - Backup file location
