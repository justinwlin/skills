# Official Runpod Agent Skills

The **official** plugin marketplace of skills for AI agents to manage GPU workloads on Runpod —
pods, serverless endpoints, jobs, templates, and volumes — via the Runpod MCP
server, `runpodctl`, and `flash`.

This repo ships **one plugin**, [`runpod`](plugins/runpod/), that bundles a router
plus six skills, the hosted Runpod MCP server config, and worked golden paths.

**Compatibility:** installs as a native plugin in **Claude Code, Codex, Gemini,
and opencode** (with auto-update), and as skills via **skills.sh** for Cursor,
Copilot, Windsurf, Cline, and 17+ other agents — all from the same manifest.

## Quick start (Claude Code)

Three steps to your first command:

```
1. /plugin marketplace add runpod/skills
2. /plugin install runpod@runpod
3. /mcp → runpod → Sign in with Runpod        # authenticate (OAuth, no key on disk)
```

Then just ask in plain English — the skill drives the tools for you:

> *"list my Runpod endpoints"*  ·  *"spin up an A100 pod"*  ·  *"deploy this handler to serverless"*

On another agent (Codex, Cursor, Gemini, …) or prefer an API key? See
[Install](#install) and [Authentication](#authentication) below.

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

Auth is needed in **two places**, and **one Runpod API key covers both**:

| What | What it needs | How |
| --- | --- | --- |
| `runpodctl` + `flash` (the CLIs) | `RUNPOD_API_KEY` env var | `export RUNPOD_API_KEY=<key>` |
| Hosted **Runpod MCP** server (infra tools) | OAuth **or** the same key | `/mcp` sign-in, **or** pass the key as a Bearer header |

**Fastest path — one key, everything:**

1. **Get an API key:** [Runpod console → Settings → API Keys](https://runpod.io/console/user/settings).
2. **Export it** — the CLIs (`runpodctl`, `flash`) now work:
   ```bash
   export RUNPOD_API_KEY=<key>
   ```
3. **Authenticate the MCP server** — pick one:
   - **OAuth (easiest, no key on disk):** in Claude Code, `/mcp` → **runpod** → *Sign in with Runpod*.
   - **Reuse the key you just set:**
     ```bash
     claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/ \
       --header "Authorization: Bearer $RUNPOD_API_KEY"
     ```

Codex and local-stdio MCP variants are in [`runpod-mcp`](plugins/runpod/skills/runpod-mcp/SKILL.md).
Companion CLIs (`hf`, `docker`, `gh`, `aws`) use their own credentials — see
[`companion-clis`](plugins/runpod/skills/companion-clis/SKILL.md). If nothing is set up, the
`runpod` skill detects it and walks you through this.

## Updating

The plugin is **versioned**: updates arrive when we cut a release (a version bump, see
the CHANGELOG). Claude Code pulls the new version in the background; if it hasn't picked
it up yet, force it manually:

| Client | Update command |
| --- | --- |
| **Claude Code** | `/plugin marketplace update runpod` then `/reload-plugins` |
| **Codex** | `codex plugin marketplace upgrade runpod` |
| **skills.sh** | re-run `npx skills add runpod/skills` |

## Uninstall

Remove the plugin (and, where applicable, the marketplace it came from):

| Client | Uninstall |
| --- | --- |
| **Claude Code** | `/plugin uninstall runpod@runpod`, then `/plugin marketplace remove runpod` |
| **Codex** | `codex plugin marketplace remove runpod` |
| **skills.sh** | `npx skills remove runpod` |

If a command reports a name mismatch, list what's installed first —
`/plugin marketplace list` (Claude Code) · `codex plugin marketplace list` (Codex) ·
`npx skills list` (skills.sh) — and use the name shown. Removing the marketplace also drops
the bundled hosted-MCP registration it added; if you configured the MCP separately, remove
that too (Claude Code: `claude mcp remove runpod`).

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
[`plugins/runpod/skills/runpod/golden-paths/`](plugins/runpod/skills/runpod/golden-paths/).

## Repository layout

```
.claude-plugin/marketplace.json   Claude Code / skills.sh marketplace manifest
.agents/plugins/marketplace.json  Codex marketplace manifest
plugins/runpod/                   the plugin (skills/ incl. runpod/golden-paths/, .mcp.json, manifests)
hooks/                            marketplace, branding & link validation
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0
