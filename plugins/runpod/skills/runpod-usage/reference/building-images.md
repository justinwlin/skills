# Building container images for Runpod

How to think about building an image for Runpod: pick the right base, layer for speed,
decide what to **bake in** vs **mount at runtime**, and match the **image contract** to your
target (pod vs serverless queue vs serverless load-balanced). CLI mechanics (login, tag,
push) live in [companion-clis docker](../../companion-clis/reference/docker.md) and
[docker.md](docker.md); this is the strategy layer.

## Start from an official Runpod base image

Build `FROM` an official **`runpod/pytorch:<tag>`** image. Two reasons:

- **torch/CUDA already match Runpod hosts**, so you don't fight driver/toolkit mismatches.
- **Runpod pre-caches official base images on its hosts.** The base layers are effectively
  already on the machine, so they don't re-download at pull time — you only ship the layers
  you add on top. Starting from a random public base throws that away.

Pin an exact tag (e.g. `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`) and build for x86:
`docker build --platform=linux/amd64 …` (Runpod hosts are x86_64 — see
[docker.md](docker.md)).

## Layer for fast, cacheable pulls

Order layers **least- to most-frequently-changing** so a code edit doesn't invalidate the
heavy dependency layers, and independent layers pull in parallel:

1. base image (`FROM runpod/pytorch:…`)
2. system deps (`apt-get …`)
3. Python deps (`pip install …`)
4. **your code last**

Unchanged layers are reused from cache; only the layers after your edit rebuild/re-pull.

## Bake in vs mount at runtime (this drives startup speed)

Only the **image** (and whatever is baked into it) lands on the host's **local disk** — fast.
When a **network volume** is attached it takes over the working directory (`/workspace` on a
pod, `/runpod-volume` on serverless); anything written there lives on **networked storage**,
which is slower — **especially for many small files**.

- **Bake into the image:** packages, libraries, and lots of small static files → local, fast.
- **Mount a volume:** large/few files (model weights, datasets), anything that must persist
  across pods, or data you stream/live-load.
- **High-throughput / I/O-bound training:**
  - **temporary / one-off run** → a **pod using local (non-network) storage** is fastest;
  - **persistent, many small files, or I/O-bound** → a **high-performance network volume**.

  See [golden path 21 — storage tiers](../../runpod/golden-paths/21-storage-tiers.md).

## Match the image contract to the target

| Target | Needs a handler? | Entry point |
| --- | --- | --- |
| **Pod** | No | your `CMD`/entrypoint — a long-running service; bind `0.0.0.0`, expose ports |
| **Serverless — queue-based** | **Yes** | `runpod.serverless.start({"handler": handler})` |
| **Serverless — load-balanced** | No (different contract) | your own **HTTP server** exposing routes (no queue handler) |

Queue vs load-balanced request/response shapes and when to pick each are covered in
[endpoint-workflows.md](endpoint-workflows.md) and golden paths
[12 (streaming)](../../runpod/golden-paths/12-serverless-streaming.md),
[14 (load-balancing)](../../runpod/golden-paths/14-load-balancing-endpoint.md), and
[17 (WebSocket)](../../runpod/golden-paths/17-serverless-websocket.md). One image can be
**dual-mode** (pod dev + serverless) — see
[golden path 09](../../runpod/golden-paths/09-custom-serverless-dev-loop/README.md).

## Test locally before deploying

- Build for the right platform: `docker build --platform=linux/amd64 …`.
- **Queue handler:** run the container and invoke `handler.py` locally (the dual-mode
  `python handler.py` loop in [golden path 09](../../runpod/golden-paths/09-custom-serverless-dev-loop/README.md))
  before pushing.
- **Load-balanced:** run the container and hit the HTTP routes locally.
- Then push ([companion-clis docker](../../companion-clis/reference/docker.md)) and deploy
  (runpodctl or runpod-mcp).
