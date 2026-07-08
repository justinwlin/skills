# Tie-break: runpod-mcp vs runpodctl on overlapping infra CRUD

## Prompt

The Runpod MCP tools are connected in my session. Two things: (a) list my pods,
and (b) create a pod from my saved template `tmpl-abc` with a CPU flavor. Which
tool for each, and why?

## Expected behavior

Per the capability matrix in `runpod/SKILL.md` (choose by capability first,
environment second):

1. **(a) list pods → runpod-mcp** — a simple structured read, and MCP is connected.
2. **(b) create a pod from a template / CPU pod → runpodctl** — even though MCP is
   connected, MCP's `create-pod` has no `templateId`, requires an image, and
   doesn't do CPU pods; `runpodctl pod create --template-id … --compute-type cpu`
   does. This is the "hand pod creation to runpodctl when it needs a capability MCP
   lacks" rule.

## Assertions

- Routes the **list** to runpod-mcp (MCP connected → prefer it for simple reads/CRUD).
- Routes the **template/CPU pod create** to runpodctl, explicitly because MCP lacks templateId/CPU.
- Does NOT blanket-route everything to MCP just because it's connected.
