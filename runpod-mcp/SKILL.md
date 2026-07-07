---
name: runpod-mcp
description: >-
  Manage Runpod infrastructure — pods, serverless endpoints, jobs, templates,
  network volumes, container-registry auth, GPU/CPU catalog, and billing — via
  the Runpod MCP server's structured tool calls. Use when the Runpod MCP tools
  (create-pod, list-endpoints, …) are connected in this session, or to connect
  them (hosted OAuth or local npx). Prefer this over runpodctl for plain infra
  CRUD when MCP is available; use runpodctl for the terminal, Hub deploys, file
  transfer, or SSH setup.
allowed-tools: Bash(npx:*), Bash(claude:*)
compatibility: Linux, macOS, Windows
metadata:
  author: runpod
  version: "1.0"
license: Apache-2.0
---

# Runpod MCP

The Runpod MCP server exposes Runpod's control plane as structured tool calls,
so an MCP-capable agent can manage infrastructure without shelling out. It is the
same Runpod REST API that `runpodctl` uses — pick MCP when its tools are
connected (typed params, structured errors, no shell quoting).

## Connect

**Hosted (recommended)** — no API key stored on disk; authenticates with the
"Sign in with Runpod" OAuth flow on first connect:

```bash
# guided installer — detects your agents and configures them
npx @runpod/mcp-server@latest add

# or configure a single client by hand (Claude Code shown)
claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/
```

Prefer your own key over OAuth? Append
`--header "Authorization: Bearer $RUNPOD_API_KEY"` — the server forwards it to the
Runpod API directly.

**Local (stdio)** — runs the server as a subprocess with your key:

```bash
claude mcp add runpod -s user -e RUNPOD_API_KEY=YOUR_KEY -- npx -y @runpod/mcp-server
```

After connecting, reconnect the client (in Claude Code, `/mcp`) and the tools
appear in the session.

## Tool surface

Structured tools, grouped by resource:

- **Pods** — list, get, create, update, start, stop, restart, delete, stream logs.
- **Serverless endpoints** — list, get, create, update, delete; list workers; list releases.
- **Jobs (serverless runtime)** — run, runsync, status, stream, cancel, retry, health, purge queue.
- **Templates** — list, get, create, update, delete.
- **Network volumes** — list, get, create, update, delete.
- **Container registry auth** — list, get, create, delete.
- **Catalog** — list/get GPU types, CPU types, data centers.
- **Billing** — scoped usage/cost breakdowns.

## Use MCP vs runpodctl

- **Use runpod-mcp** when the tools are connected AND the task is infra CRUD or a
  serverless job call the server exposes. Cap large job/log output to a file.
- **Use runpodctl instead** for: anything MCP has no tool for — **Hub**
  browse/deploy, **`send`/`receive`** file transfer, **SSH** key management,
  **`doctor`** setup, **model cache** — or any shell-only agent, or when the user
  wants a reproducible command.
- **Hand pod creation to runpodctl** when it needs a capability MCP's create-pod
  lacks: **from a template** (`--template-id`), a **CPU** pod (`--compute-type
  cpu`), or a **multi-GPU priority list**. MCP's v2 create-pod requires an image
  and takes a single GPU type — fine for a simple one-image/one-GPU pod, but defer
  the richer cases even when MCP is connected.
- **Not this lane:** writing/deploying your own Python (→ flash); downloading
  models or building/pushing images (→ companion-clis).

For concepts (pods vs serverless, GPU selection, storage), read
`../runpod-usage/`.
