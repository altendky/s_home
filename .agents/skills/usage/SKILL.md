---
name: usage
description: "Show current Anthropic subscription usage using the local agent-usage command and present its output as a Markdown table. Use for Anthropic or Claude subscription usage requests."
---

# Anthropic subscription usage

Show the user's current Anthropic subscription usage by running the installed
`agent-usage` command through the host's shell interface:

```sh
agent-usage
```

Present the returned data as a Markdown table, retaining any reported usage
windows, limits, and reset times. If the command is unavailable or fails, report
the error; do not infer account usage or substitute another provider's data.
