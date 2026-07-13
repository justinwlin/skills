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

## First run — get a control plane set up (don't just limp on a fallback)

Infra tasks (create/list/manage pods, endpoints, jobs, volumes) need a working control-plane
lane: the **Runpod MCP server** (structured tools) or **runpodctl** (CLI). On the first infra
request, check what's actually connected and **proactively help the user get set up** — use a
working lane so you're never blocked, but **don't quietly limp along on a partial fallback when a
quick one-time setup step would give them the right lane.** Push them to get properly set up
where it makes sense; keep trying whatever works in the meantime.

**One step covers most lanes.** `export RUNPOD_API_KEY=…` (from
https://runpod.io/console/user/settings) makes **runpodctl, flash, and the local-stdio MCP** all
work at once. The **hosted MCP is the one exception** — it needs its own **`/mcp` → "Sign in
with Runpod"** (or pass that same key as an `Authorization: Bearer` header). So: **one key for
the CLIs, one sign-in for the hosted MCP** — authing the MCP does *not* by itself set up the CLIs,
and vice-versa. Recommend the single `export` first; it's the closest thing to one-step setup.

What to do:
1. **A lane is already connected** — MCP tools callable, or `runpodctl user` works → use it.
2. **MCP installed but unauthenticated** — common right after installing this plugin (it bundles
   the hosted server, but the tools stay inert until sign-in). **Don't silently ignore it and
   drop to a fallback** — tell the user to authenticate: Claude Code `/mcp` → `runpod` → *Sign in
   with Runpod*; Codex `codex mcp add runpod --transport http https://mcp.getrunpod.io/`. It's the
   nicer lane once live.
3. **Nothing connected** — **stop and set them up** (don't guess or fake a result). Recommend the
   one key first (`export RUNPOD_API_KEY=…` → unlocks runpodctl + flash), then the hosted-MCP
   sign-in if they want structured tools. Or install a lane: `curl -sSL https://cli.runpod.net |
   bash` (runpodctl) / `npx @runpod/mcp-server@latest add` (MCP).
4. **Only a fallback lane is available** — e.g. runpodctl works but they wanted MCP (or vice-
   versa). **Use what works to make progress, and offer the one-time setup** that gives them the
   intended lane, so it's smoother next time. Progress now, but nudge toward the proper setup.

Full setup: **runpod-mcp** (Connect) and `runpod-usage/reference/getting-started.md`. Get one lane
green, then continue with the routing below.

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

Both drive the same Runpod API, so they overlap on infra CRUD. Choose by
**capability first, environment second**:

- **MCP wins on convenience** for simple, structured operations — reads and basic
  CRUD — when its tools are connected (typed params, no shell quoting).
- **runpodctl takes over when an operation needs a capability MCP lacks** — even
  if MCP is connected — and is the only option for a shell-only agent or when the
  user wants a reproducible command.

Capability matrix (pick the preferred lane per operation):

| Operation | Preferred lane | Why |
| --- | --- | --- |
| List/get anything; start/stop/restart/delete a pod; simple CRUD on endpoints, templates, volumes, registries; catalog; billing | **runpod-mcp** if connected, else runpodctl | Simple structured ops — MCP is typed and convenient |
| Create a **simple** pod (one image + one GPU) | **runpod-mcp** if connected, else runpodctl | Both handle it |
| Create a pod **from a template**, a **CPU** pod, or with a **multi-GPU priority list** | **runpodctl** | MCP's v2 create-pod has no `templateId`, requires an image, and narrows to a single GPU type |
| Deploy from the **Hub** | **runpodctl** | MCP has no Hub tools |
| **File transfer** (`send`/`receive`), **SSH** keys/info, **`doctor`** setup, **model** cache | **runpodctl** | MCP has no tool for these |
| Invoke a serverless job (`run`/`runsync`/status/stream) | **runpod-mcp** if connected, else runpodctl | MCP has first-class job tools |

Rule of thumb: **default to MCP for the easy stuff, hand off to runpodctl the
moment an op needs a flag/feature MCP doesn't expose.**

## Deploying a workload (the golden loop)

For any "get <X> running on Runpod" task, follow the **development loop** in
`runpod-usage/reference/development-loop.md`: decide pod vs serverless → **prefer a
prebuilt template / Hub worker over building from scratch** → provision → set up
(only if from-scratch) → **verify with a real request from outside** ("Running"/
"ready" ≠ serving) → deliver → cost-guard + teardown. It branches to two sub-loops:

- **Service you open at a URL** (Ollama, ComfyUI, dev box) → `pod-workflows.md`
  (ports + env + volume at creation, SSH-exec install, bind `0.0.0.0`, poll the
  proxy URL). Execute in the runpodctl lane.
- **Request/response API that scales to zero** (Whisper, inference) →
  `endpoint-workflows.md` (Hub worker vs flash vs custom image; invoke `/run`/
  `/runsync`; poll job status).

## Worked examples (golden paths)

**Nineteen** end-to-end, **live-verified** scenarios live in
[`../../golden-paths/README.md`](../../golden-paths/README.md) — the yardstick for "can
an agent finish the job", with real commands + observed output to copy from. When a
task matches one, **open its golden path first** instead of re-deriving it:

| Want to… | Golden path |
| --- | --- |
| Run a server (Ollama/ComfyUI) on a pod at a URL | [01](../../golden-paths/01-ollama-pod.md), [02](../../golden-paths/02-comfyui-pod/README.md) |
| Deploy a serverless model endpoint (Hub / flash / custom image) | [03](../../golden-paths/03-whisper-endpoint/README.md), [05](../../golden-paths/05-model-to-endpoint-pipeline.md) |
| Call a ready hosted model (no deploy) | [11 — Public Endpoints](../../golden-paths/11-public-endpoints.md) |
| Fine-tune, then serve the result | [04](../../golden-paths/04-finetune-pod.md), [08](../../golden-paths/08-finetune-to-serverless.md) |
| Interactive dev box (SSH / VS Code) | [06](../../golden-paths/06-dev-pod.md) |
| Move data pod → volume → serverless | [07](../../golden-paths/07-network-volume-handoff.md) |
| **Custom serverless when flash isn't enough** (dual-mode image dev loop) | [09](../../golden-paths/09-custom-serverless-dev-loop/README.md) |
| **High availability / multi-region** serverless (multi-volume + data sync) | [10](../../golden-paths/10-multi-region-ha-serverless.md), [19 (3-region)](../../golden-paths/19-three-region-same-file.md) |
| Stream output incrementally (`/stream`) | [12](../../golden-paths/12-serverless-streaming.md) |
| Tune autoscaling / raise per-worker throughput | [13 (autoscaling)](../../golden-paths/13-autoscaling-tuning.md), [18 (concurrency)](../../golden-paths/18-concurrent-handler.md) |
| Load-balancing / HTTP-server or WebSocket worker | [14 (LB)](../../golden-paths/14-load-balancing-endpoint.md), [17 (WebSocket)](../../golden-paths/17-serverless-websocket.md) |
| Get notified on job completion (push, not poll) | [16 — webhooks](../../golden-paths/16-serverless-webhooks.md) |
| Check health / debug a failing endpoint | [15 — monitor & debug](../../golden-paths/15-monitor-and-debug.md) |

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
