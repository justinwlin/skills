# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Overview

This is a **skills repository** for AI agents (Claude Code, Cursor, Copilot, etc.)
to work with Runpod. It contains no application code — only skill definition files
(`SKILL.md`) plus supporting reference docs. Skills teach agents how to manage GPU
workloads across several backends and how Runpod works conceptually.

Skills are installed by users via `npx skills add runpod/skills` (see
[skills.sh](https://skills.sh/)).

## Architecture: a router + lanes

The repository is organized as one **entrypoint** that routes to specialized
**lanes**. `runpod/` is the router: an agent reads it first when the right lane is
unclear, then follows its decision table into a lane's `SKILL.md`.

```
runpod/            router / entrypoint — decides the lane
runpod-mcp/        manage infra via the Runpod MCP server (structured tool calls)
runpodctl/         manage infra via the CLI (+ Hub, file transfer, SSH, doctor)
flash/             write & deploy your own code on Runpod serverless (@remote)
companion-clis/    prerequisite CLIs (hf, gh, docker, aws)
runpod-usage/      conceptual knowledge ("how Runpod works") — not a tool
  reference/*.md   detailed topics, loaded on demand
```

**runpod-mcp and runpodctl overlap** — both drive the same Runpod REST API for the
same infra CRUD. They are disambiguated by environment, not feature: prefer
runpod-mcp when its tools are connected in the session; use runpodctl for
shell-only agents and for CLI-only capabilities (Hub, `send`/`receive`, SSH,
`doctor`, models). Keep this rule consistent across the router and both skills'
descriptions when editing.

## Skill file format

`SKILL.md` files use YAML frontmatter:
- `name`, `description` — skill identity. The `description` is the routing surface
  (always in the agent's context), so keep it 1–2 sentences and, for overlapping
  skills, name the sibling and when to defer to it.
- `allowed-tools` — tool permissions (e.g., `Bash(runpodctl:*)`). Omit for
  knowledge-only skills.
- `user-invocable` — set for skills a user invokes directly.
- `compatibility`, `metadata` (author, version), `license`.

The body is markdown the agent consumes. Follow **progressive disclosure**: keep
the `SKILL.md` body small (a decision table + the 80% patterns) and push long
tables / deep explanations into `reference/*.md` that the body links to and the
agent opens only when needed.

## Conventions

- **Spelling:** "Runpod" (capital R). The CLI command is `runpodctl` (lowercase).
- **Auth:** everything unifies on `RUNPOD_API_KEY`; the MCP hosted server is the
  exception (OAuth "Sign in with Runpod"). Companion CLIs use their own creds.
- **License:** Apache-2.0.
