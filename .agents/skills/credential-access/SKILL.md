---
name: credential-access
description: Supply a 1Password credential to an authorized command or script without exposing its value to agent-visible output. Use when a task needs an existing secret via op CLI, including discovering the required field metadata; documentation-only requests do not require retrieving secrets.
---

# Credential Access

Keep secret values flowing within the execution environment, outside agent
context. Environment variables help avoid transcript exposure; they are not a
guarantee of isolation from other processes or users on the host.

## Resolve Only What The Task Needs

Use the current project's applicable credential documentation or the user's
supplied reference to identify the needed vault, item, and field. Do not assume
a particular repository, vault, account, or item name, or search unrelated
projects for secrets.

Establish the needed item/field and the authorized consumer operation before
retrieval. Check CLI availability and authentication without printing a secret.
If field layout is unknown, filter metadata within the execution environment
and return only the needed field IDs, labels, and types. Do not return raw item
JSON or field values to the agent.

## Prepare And Invoke The Consumer

1. Have the consumer read a task-specific environment variable. Keep secret
   values out of its source, arguments, debug traces, exceptions, HTTP/header
   dumps, and normal output. Report only the nonsecret result needed by the user.
2. For a temporary standalone Python consumer, follow the host's PEP 723 and
   `uv run` conventions. Reuse the session directory under `/tmp/agents/` (or
   `${TMPDIR}/agents/`) and clean up temporary code when no longer needed.
3. Run `op read` through a checked shell assignment with tracing disabled.
   Check its exit status and, for a required credential, a nonempty result
   before exporting the variable and invoking the consumer. Use a subshell to
   limit the variable's lifetime. Use the checked invocation below.
4. Do not use an unchecked `VAR="$(op read ...)" command` or
   `op read ... | VAR=$(cat) command` as a failure guard: the command can run even
   when retrieval fails. Report missing authentication, denied access, or an
   empty required field without retrying through a different credential path.
5. Report success only from the consumer's outcome, not from retrieving a value.

Never print `op read` output, use `op item get --fields password` as an
agent-visible lookup, write secret values into temporary files, embed them in
command arguments, or dump the environment. Use a boolean presence check when
checking injection. Keep helper code and logs free of secrets before reading
them back into context.

## Checked Invocation

Replace the reference and consumer with those established for the task. The
consumer must read `TASK_SECRET` from its environment, without logging it:

```bash
(
  set +x
  TASK_SECRET="$(op read 'op://<vault>/<item>/<field>' --no-newline)" || exit
  if [[ -z "$TASK_SECRET" ]]; then
    printf '%s\n' 'Required credential is empty' >&2
    exit 1
  fi
  export TASK_SECRET
  ./consumer
)
```

For multiple required secrets, check each retrieval before launching the
consumer. Shell command substitution removes trailing newlines; use a
task-specific procedure for binary secrets or values whose exact trailing
newlines must be preserved.

## Other Credential Flows

An interactive browser login needs a credential-entry mechanism that keeps
values outside agent context or a user-authenticated session. Do not paste
secrets through agent messages or tools that expose their arguments.

Creating/rotating credentials, exporting key files, and changing unrelated
service access are separate operations requiring their own task scope and
appropriate handling. Loading this skill does not authorize them. Follow the
specific procedure when the user's task actually requires such an operation.
