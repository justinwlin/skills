# Runpod Agent Skills

A plugin marketplace of skills for AI agents to manage GPU workloads on Runpod —
pods, serverless endpoints, jobs, templates, and volumes — via the Runpod MCP
server, `runpodctl`, and `flash`.

This repo ships **one plugin**, [`runpod`](plugins/runpod/), that bundles a router
plus six skills, the hosted Runpod MCP server config, and worked golden paths.

## Install

Pick whichever fits your agent — both read the same repo.

### As a plugin (Claude Code, Codex, Gemini, opencode, …)

Native install with auto-update:

```
/plugin marketplace add runpod/skills
/plugin install runpod@runpod
```

Installing the plugin also wires up the **hosted Runpod MCP server** (via the
bundled [`.mcp.json`](plugins/runpod/.mcp.json)) — no separate MCP setup.

### With skills.sh (Cursor, Copilot, Windsurf, Cline, + 17 others)

```bash
npx skills add runpod/skills
```

skills.sh reads the same [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
manifest, so this installs the same six skills. To grab a single skill, point at
its path:

```bash
npx skills add https://github.com/runpod/skills/tree/main/plugins/runpod/skills/runpodctl
```

## What's inside

Start with the **`runpod`** router; it points at the right lane.

| Skill | Use it for |
| --- | --- |
| [`runpod`](plugins/runpod/skills/runpod/SKILL.md) | Router / entrypoint. Start here when the right skill is unclear. |
| [`runpod-mcp`](plugins/runpod/skills/runpod-mcp/SKILL.md) | Manage infra via the Runpod **MCP server**'s structured tool calls. |
| [`runpodctl`](plugins/runpod/skills/runpodctl/SKILL.md) | Manage infra from the **CLI**, plus Hub, file transfer, SSH, `doctor`. |
| [`flash`](plugins/runpod/skills/flash/SKILL.md) | **Write and deploy your own code** on Runpod serverless (`@remote`). |
| [`companion-clis`](plugins/runpod/skills/companion-clis/SKILL.md) | Prerequisite CLIs: `hf`, `docker`, `gh`, `aws`. |
| [`runpod-usage`](plugins/runpod/skills/runpod-usage/SKILL.md) | **Concepts** — pods/serverless, containers, storage, GPU selection, gotchas. |

See the plugin's [README](plugins/runpod/README.md) for the full guide, the
development loop, and setup. Worked end-to-end examples live in
[`plugins/runpod/golden-paths/`](plugins/runpod/golden-paths/).

## Setup

Everything unifies on a single **`RUNPOD_API_KEY`**
(https://runpod.io/console/user/settings); `runpodctl doctor` stores it + sets up
SSH. The hosted MCP server uses "Sign in with Runpod" OAuth instead. Companion
CLIs use their own credentials.

## Repository layout

```
.claude-plugin/marketplace.json   Claude Code / skills.sh marketplace manifest
.agents/plugins/marketplace.json  Codex marketplace manifest
plugins/runpod/                   the plugin (skills/, golden-paths/, .mcp.json, manifests)
hooks/                            marketplace + branding validation
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0
