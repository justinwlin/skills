# Runpod Agent Skills

Skills for AI agents to manage GPU workloads on Runpod.

## Installation

```bash
npx skills add runpod/skills
```

Works with Claude Code, Cursor, GitHub Copilot, Windsurf, Cline, and
[17+ other AI agents](https://skills.sh/).

## Which skill?

Start with **`runpod`** — the router. It reads your task and points to the right
lane below. If you already know the lane, go straight to it.

| Skill | Use it for |
| --- | --- |
| [`runpod`](runpod/SKILL.md) | Router / entrypoint. Start here when the right skill is unclear. |
| [`runpod-mcp`](runpod-mcp/SKILL.md) | Manage infra (pods, endpoints, jobs, templates, volumes, catalog, billing) via the Runpod **MCP server**'s structured tool calls. |
| [`runpodctl`](runpodctl/SKILL.md) | Manage infra from the **CLI**, plus Hub deploys, file transfer (`send`/`receive`), SSH, and `doctor` setup. |
| [`flash`](flash/SKILL.md) | **Write and deploy your own code** on Runpod serverless — `@remote`/`@Endpoint`, `flash dev`, `flash deploy`. |
| [`companion-clis`](companion-clis/SKILL.md) | Prerequisite CLIs: `hf` (models), `docker` (images), `gh` (repos/releases), `aws` (S3 to volumes). |
| [`runpod-usage`](runpod-usage/SKILL.md) | **Concepts** — how pods/serverless work, building containers, storage, GPU selection, gotchas. |

**runpod-mcp vs runpodctl:** both drive the same Runpod API for the same infra
CRUD. Prefer `runpod-mcp` when its tools are connected in your session; use
`runpodctl` for the terminal, Hub, file transfer, SSH, or `doctor`.

## Setup

Everything unifies on a single **`RUNPOD_API_KEY`**
(https://runpod.io/console/user/settings):

```bash
runpodctl doctor          # CLI: store the key + SSH
```

The hosted MCP server is the exception — it uses the "Sign in with Runpod" OAuth
flow, so no key is stored on disk (see [`runpod-mcp`](runpod-mcp/SKILL.md)).
Companion CLIs (`hf`, `gh`, `docker`, `aws`) use their own credentials.

## Usage

Ask your AI agent:

- "Create a pod with an RTX 4090"
- "Deploy a serverless endpoint from this image"
- "Which GPU should I use for a 13B model?"
- "Write an `@remote` function and run it on a GPU"
- "Download a model, containerize it, and deploy it"

## URLs

- **Pod:** `https://<pod-id>-<port>.proxy.runpod.net` (e.g. `https://abc123xyz-8888.proxy.runpod.net`)
- **Serverless:** `https://api.runpod.ai/v2/<endpoint-id>/{run|runsync|health|status/<job-id>}`

More in [`runpod-usage/reference/networking.md`](runpod-usage/reference/networking.md).

## Structure

```
runpod/            router / entrypoint
runpod-mcp/        Runpod MCP server (structured tool calls)
runpodctl/         Runpod CLI (+ Hub, transfer, SSH, doctor)
flash/             write & deploy your own code (@remote)
companion-clis/    hf / gh / docker / aws prerequisites
runpod-usage/      concepts + reference/*.md
```

## License

Apache-2.0
