# Runpod Agent Skills

A plugin marketplace of skills for AI agents to manage GPU workloads on Runpod —
pods, serverless endpoints, jobs, templates, and volumes — via the Runpod MCP
server, `runpodctl`, and `flash`.

This repo ships **one plugin**, [`runpod`](plugins/runpod/), that bundles a router
plus six skills, the hosted Runpod MCP server config, and worked golden paths.

**Compatibility:** installs as a native plugin in **Claude Code, Codex, Gemini,
and opencode** (with auto-update), and as skills via **skills.sh** for Cursor,
Copilot, Windsurf, Cline, and 17+ other agents — all from the same manifest.

## Install

Same repo, one manifest — pick your agent below. Every route installs the same
router + six skills, plus a hosted **Runpod MCP server** for control-plane tools.
Then [authenticate](#authentication).

### Claude Code

```
/plugin marketplace add runpod/skills
/plugin install runpod@runpod
/reload-plugins
```

Installing **also wires up the hosted Runpod MCP server** (via the bundled
[`.mcp.json`](plugins/runpod/.mcp.json)) — no separate MCP setup. Authenticate it:
`/mcp` → **runpod** → *Sign in with Runpod* (OAuth; no key on disk).

**Verify:** `/plugin` shows **Runpod** under *Installed*; then ask *"list my Runpod
endpoints"* — it should call the MCP `list-endpoints` tool.

### Codex

```bash
codex plugin marketplace add https://github.com/runpod/skills.git
codex /plugins        # → open the "Runpod" marketplace tab → Runpod → Install (reload if prompted)
```

Manage the source: `codex plugin marketplace list` · `… upgrade runpod` · `… remove runpod`.

Codex may **not** auto-wire the bundled MCP — if the `runpod` MCP tools don't appear
after install, add the hosted server manually:

```bash
codex mcp add runpod --transport http https://mcp.getrunpod.io/
```

**Verify:** ask a Runpod task (the skill/router should answer); once the MCP is added,
*"list my Runpod endpoints"* should call a tool.

### Everything else — Cursor, Copilot, Windsurf, Cline, opencode, Gemini (+17)

Install the skills via **skills.sh** (reads the same
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)):

```bash
npx skills add runpod/skills
# just one skill:
npx skills add https://github.com/runpod/skills/tree/main/plugins/runpod/skills/runpodctl
```

Gemini can also install natively via the bundled
[`gemini-extension.json`](plugins/runpod/gemini-extension.json) (see your client's
extension docs). For these clients, add the **MCP server** yourself — the guided
installer configures most agents:

```bash
npx @runpod/mcp-server@latest add     # detects your agent + sets up the hosted MCP (OAuth)
```

See [`runpod-mcp/SKILL.md`](plugins/runpod/skills/runpod-mcp/SKILL.md) for hosted vs
local (stdio) MCP setup and all client options.

## Authentication

The plugin includes a hosted **Runpod MCP server** (create/list/manage pods, endpoints,
jobs, volumes) — it needs credentials before its tools work. Pick one:

- **API key** *(recommended)* — get one from the
  [Runpod console](https://runpod.io/console/user/settings), then `export RUNPOD_API_KEY=…`.
  This covers **runpodctl** and **flash** directly. To use the key for the **MCP** (instead of
  OAuth), add the hosted server with a Bearer header:
  ```bash
  claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/ \
    --header "Authorization: Bearer $RUNPOD_API_KEY"
  ```
  (Codex + local-stdio variants in [`runpod-mcp`](plugins/runpod/skills/runpod-mcp/SKILL.md).)
- **OAuth** — or sign in interactively: in Claude Code, `/mcp` → `runpod` → *Sign in with
  Runpod* (no key on disk). This authenticates the hosted MCP only, not the CLIs.

Companion CLIs (`hf`, `docker`, `gh`, `aws`) use their own credentials. If nothing is set
up, the `runpod` skill detects it and walks you through this.

## Updating

The plugin is **commit-tracked**: Claude Code auto-updates it in the background when the
repo has a newer commit. If it hasn't picked up a change yet, update manually:

| Client | Update command |
| --- | --- |
| **Claude Code** | `/plugin marketplace update runpod` then `/reload-plugins` |
| **Codex** | `codex plugin marketplace upgrade runpod` |
| **skills.sh** | re-run `npx skills add runpod/skills` |

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

## Repository layout

```
.claude-plugin/marketplace.json   Claude Code / skills.sh marketplace manifest
.agents/plugins/marketplace.json  Codex marketplace manifest
plugins/runpod/                   the plugin (skills/, golden-paths/, .mcp.json, manifests)
hooks/                            marketplace, branding & link validation
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0
