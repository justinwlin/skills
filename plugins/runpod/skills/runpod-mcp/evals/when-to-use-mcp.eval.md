# When to use the MCP lane (and when to defer)

## Prompt

The Runpod MCP tools are connected. I need to: (1) list my serverless endpoints,
(2) deploy a vLLM worker from the Runpod Hub, and (3) grab a pod's recent logs.
Handle each.

## Expected behavior

Per `runpod-mcp/SKILL.md`:

1. **(1) list endpoints → runpod-mcp** — a structured read the server exposes; MCP
   is connected, so prefer it.
2. **(2) deploy from the Hub → runpodctl** — MCP has **no Hub tools**; Hub deploy
   is runpodctl-only, even with MCP connected.
3. **(3) pod logs → runpod-mcp** — the server exposes pod log streaming; a
   structured read is a good fit.

## Assertions

- Routes the endpoint **list** and the **pod logs** to runpod-mcp (connected → structured reads).
- Routes the **Hub deploy** to runpodctl, explicitly because MCP has no Hub tools.
- Does NOT try to do the Hub deploy through MCP.
