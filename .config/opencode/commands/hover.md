---
description: Monitor orchestrated workers after cancelling orchestrator_run
agent: delegate
---

# Hover Over Worker Sessions

Monitor orchestrated worker sessions after the supervising `orchestrator_run` operation was manually cancelled.

**Optional worker session IDs:** `$ARGUMENTS`

## Safety Rules

- Never send a command to a worker session. Never send a message except for the single conditional final-summary prompt permitted in step 5.
- Never use `orchestrator_run` for a worker whose latest `orchestrator_get_session_state` status is `busy`, `retry`, or `unknown`.
- Treat `busy` conservatively: the orchestrator maps unknown upstream statuses to `busy`.
- Treat missing, unavailable, errored, or ambiguous status as non-idle and do not use `orchestrator_run` for that worker.
- Use `orchestrator_list_sessions` only for discovery and overview. Only `orchestrator_get_session_state` may establish that a worker is idle.
- Timer sessions are not workers. Keep every timer session ID separate from the fixed worker set.
- Do not answer permission or question requests automatically. Relay them to the user.

## Process

1. Use `orchestrator_list_commands` and `orchestrator_list_agents` once before the first `orchestrator_run` operation.
   - Use these operations only to satisfy routing/discovery policy and note the environment.
   - Do not stop if the `bash` command or `Bash` agent is unavailable.

2. Determine the worker set before creating any timer sessions.
   - If `$ARGUMENTS` contains session IDs, parse comma- or whitespace-separated IDs and use exactly those sessions. Treat collection-intent words such as `collect`, `summarize`, or `final` as modifiers, not session IDs.
   - Otherwise use `orchestrator_list_sessions` with arguments `limit: 100`.
   - Select sessions from the current directory context that have `launched_by_you: true` and currently appear `busy` or `retry`.
   - Treat a listed `busy` status as possibly representing an unknown upstream status.
   - If no candidate exists, or the intended workers are ambiguous, show the likely candidates and ask the user to rerun `/hover` with explicit session IDs. Do not guess.
   - Once selected, keep the worker set fixed. Never add subsequently created timer sessions to it.

3. Begin a monitoring cycle.
   - Use `orchestrator_list_sessions` with arguments `limit: 100` for an overview.
   - For every unresolved worker, use `orchestrator_get_session_state` with arguments `session_id: <worker>`.
   - Report concise changes in status, pending-message count, last activity, and recent running or failed tool calls.

4. Handle each worker according to its detailed state.
   - `busy`: keep monitoring. Do not use `orchestrator_run` for it.
   - `retry`: report the attempt, reason, and next retry time; keep monitoring. Do not use `orchestrator_run` for it.
   - `unknown`, missing, unavailable, errored, or ambiguous state: report it as blocked and do not use `orchestrator_run`.
   - `idle` with `pending_message_count > 0`: report that the session is idle with an unanswered message and needs user attention. Do not use `orchestrator_run`.
   - `idle` with `pending_message_count == 0`: make that `orchestrator_get_session_state` operation with arguments `session_id: <worker>` the immediate predecessor to a status-only `orchestrator_run` operation with arguments `session_id: <worker>`. Do not use any intervening operation and do not pass `message`, `command`, or `agent`.

5. Handle a status-only worker result.
   - `completed` with a response payload: capture and report the worker response, then mark the worker resolved.
   - `completed` with no response payload: send exactly one final-summary prompt only when all of these conditions hold:
     - The status-only operation's immediate predecessor was `orchestrator_get_session_state` with arguments `session_id: <worker>`, and it confirmed `idle` with `pending_message_count == 0`.
     - No permission or question is pending.
     - Either the user explicitly requested final collection in `$ARGUMENTS` with wording such as `collect`, `summarize`, or `final`, or the command context clearly implies that final collection is desired.
   - When those conditions hold, use `orchestrator_run` exactly once with arguments `session_id: <worker>` and `message: "Please provide a concise end-result summary for the work you just completed. Include: outcome, important files/artifacts changed or discovered, verification performed if any, and any remaining blockers. Do not start new work."` This is a message to the confirmed-idle worker, not a command, and it must not include an `agent`.
   - This final-summary operation can block like any other `orchestrator_run`. If it appears stuck, tell the user they may press esc-esc and rerun `/hover`.
   - Handle the final-summary operation's result normally: capture a completed response, or relay a permission/question request. Do not send another final-summary prompt.
   - If final-summary prompting is not appropriate, record the outcome as `completed/idle, no final assistant text; needs manual inspection or explicit collect-final rerun` and mark the worker resolved rather than treating it as a fully satisfying final result.
   - `permission_required`: relay the request and mark the worker as needing user input.
   - `question_required`: relay the questions and mark the worker as needing user input.
   - On an error, report it and leave the worker unresolved; do not send replacement work.

6. If any workers remain `busy` or `retry`, wait approximately 60 seconds by creating a fresh timer session:

   - operation: `orchestrator_run`
   - arguments: `message: "Timer only: wait approximately 60 seconds, then reply exactly TIMER COMPLETE. Do not inspect files, run tools, or interact with worker sessions."`

   - Record the returned timer session ID and exclude it permanently from the worker set.
   - Do not attach the timer to any worker session.
   - If the timer requests permission or asks a question, identify it clearly as a timer request, relay it to the user, and stop rather than answering automatically.
   - After the timer completes, return to step 3.

7. Stop when every worker has either:
   - returned a completed result,
   - requested permission or answers,
   - become blocked by an unavailable/invalid state, or
   - reached idle with unanswered messages requiring user attention.

Finish with a compact table containing each worker session ID, final observed state, last activity, and outcome.
