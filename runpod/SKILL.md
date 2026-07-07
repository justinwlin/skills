---
name: runpod
description: >-
  Start here for any Runpod task — running GPU/CPU pods, deploying serverless
  endpoints, templates, network volumes, building images, or understanding how
  Runpod works. Routes the request to the right Runpod skill (runpod-mcp,
  runpodctl, flash, companion-clis, or runpod-usage). Use when it is unclear
  which Runpod skill applies.
metadata:
  author: runpod
  version: "1.0"
license: Apache-2.0
---

# Runpod (router)

The entrypoint for the Runpod skills. This skill does no work itself — it picks
the right lane and hands off. Read the matching skill's `SKILL.md` next.

## The lanes

| Lane | Use it for |
| --- | --- |
| **runpod-mcp** | Manage infra (pods, endpoints, jobs, templates, volumes, registries, catalog, billing) via **structured tool calls** — when the Runpod MCP tools are connected in this session. |
| **runpodctl** | Manage the same infra from a **terminal/CI/script**, plus the things only the CLI does: Hub browse/deploy, `send`/`receive` file transfer, SSH keys, `doctor` setup, model cache. |
| **flash** | **Write Python** that runs on Runpod serverless — `@remote`/`@Endpoint` functions, `flash dev` hot-reload, `flash deploy`. Code-first, not infra management. |
| **companion-clis** | **Prerequisite artifacts**: download a model (`hf`), build/push an image (`docker`), repos/releases (`gh`), move data to a network volume over S3 (`aws`). |
| **runpod-usage** | **Understand** how Runpod works before acting — pods vs serverless, building a container, storage, GPU selection, gotchas. Knowledge only. |

## How to route

1. **Conceptual question, or an unmade design choice** (serverless vs pod? which
   GPU? bake the model or mount a volume?) → read **runpod-usage** first, then
   continue with the answer.
2. **Write/iterate/ship your own code on Runpod GPUs** → **flash**.
3. **Produce an artifact** (download a model, build+push an image, create a repo
   release, sync data to a volume) → **companion-clis**.
4. **Manage infrastructure** (create/list/update/delete pods, endpoints,
   templates, volumes; list GPUs/data centers; run a serverless job; billing):
   - Capability only the CLI has — **Hub, `send`/`receive`, SSH keys, `doctor`,
     model cache** → **runpodctl**.
   - Otherwise, if the Runpod **MCP tools are connected** in this session
     (`create-pod`, `list-endpoints`, … are available) → **runpod-mcp**.
   - Otherwise (shell-only agent, no MCP) → **runpodctl**.

### runpod-mcp vs runpodctl (the overlap)

Both drive the same Runpod REST API for the same infra CRUD, so pick by
environment, not by feature:

- **Prefer runpod-mcp** when its tools are already connected — structured params,
  typed errors, no shell quoting.
- **Use runpodctl** when there is no MCP connection, when the user wants a
  copy-pasteable command/script, or for CLI-only capabilities (Hub, file
  transfer, SSH, `doctor`, models).

## Multi-lane tasks

Sequence is always **understand → produce artifacts → manage infra → verify**,
because infra can only reference artifacts that already exist. Keep each step in
one lane, and switch lanes at credential boundaries.

Example — "deploy `openai/gpt-oss-20b` to a serverless endpoint":
1. **runpod-usage** — serverless vs pod, GPU tier for 20B, bake vs mount vs cache.
2. **companion-clis** — `hf download …`, `docker build --platform=linux/amd64 …`, `docker push`.
3. **runpod-mcp** or **runpodctl** — create the endpoint referencing the image + GPU pool.
4. Same infra lane — invoke the endpoint / check status to verify.

## Auth

Everything is one key: **`RUNPOD_API_KEY`** (https://runpod.io/console/user/settings).
Each lane just makes that key resolvable — `runpodctl doctor`, `flash login`, MCP
stdio env var, or MCP hosted "Sign in with Runpod" (OAuth, no key on disk).
Companion CLIs use their **own** credentials (HuggingFace token, GitHub auth,
Docker Hub PAT, Runpod **S3** keys for `aws`) — do not reuse `RUNPOD_API_KEY` for
those.
