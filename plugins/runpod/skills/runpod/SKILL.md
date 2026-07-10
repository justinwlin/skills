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

Ten end-to-end, mostly **live-verified** scenarios live in
[`../../golden-paths/README.md`](../../golden-paths/README.md) — the yardstick for "can
an agent finish the job", with real commands + observed output to copy from. When a
task matches one, **open its golden path first** instead of re-deriving it:

| Want to… | Golden path |
| --- | --- |
| Run a server (Ollama/ComfyUI) on a pod at a URL | [01](../../golden-paths/01-ollama-pod.md), [02](../../golden-paths/02-comfyui-pod/README.md) |
| Deploy a serverless model endpoint (Hub / flash / custom image) | [03](../../golden-paths/03-whisper-endpoint/README.md), [05](../../golden-paths/05-model-to-endpoint-pipeline.md) |
| Fine-tune, then serve the result | [04](../../golden-paths/04-finetune-pod.md), [08](../../golden-paths/08-finetune-to-serverless.md) |
| Interactive dev box (SSH / VS Code) | [06](../../golden-paths/06-dev-pod.md) |
| Move data pod → volume → serverless | [07](../../golden-paths/07-network-volume-handoff.md) |
| **Custom serverless when flash isn't enough** (dual-mode image dev loop) | [09](../../golden-paths/09-custom-serverless-dev-loop/README.md) |
| **High availability / multi-region** serverless (multi-volume + data sync) | [10](../../golden-paths/10-multi-region-ha-serverless.md) |

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
