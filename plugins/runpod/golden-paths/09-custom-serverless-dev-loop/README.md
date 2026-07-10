# Golden path 09 — custom serverless the hard way (iterate in a pod, then flip to serverless)

**Goal:** ship a **custom** serverless endpoint when the easy routes don't fit — no
Hub worker exists, and `flash`'s decorator model can't express what you need (custom
system packages, a specific torch/CUDA, a bespoke model-load, non-trivial startup).
The trick: **one image, one handler, two run modes** — develop the handler
*interactively on a GPU pod* (`python handler.py` in a loop), then flip a single env
var (`MODE_TO_RUN=serverless`) so the **exact same code** becomes an endpoint.
Worked example: a whisper **speech → text** handler.
**Status:** ⚠️ **spec (document-only, not yet live-verified).** The flow and the
[`template/`](template/) files are grounded in a proven public base
([justinwlin/Runpod-GPU-And-Serverless-Base](https://github.com/justinwlin/Runpod-GPU-And-Serverless-Base))
and the already-live-verified paths ([03](../03-whisper-endpoint/README.md) whisper,
[05](../05-model-to-endpoint-pipeline.md) docker→endpoint, [07](../07-network-volume-handoff.md)
volume handoff). The exact flags/outputs below still need a real end-to-end run —
each ⓥ tag marks what a live run should confirm.
**Lane(s):** runpodctl (pod + serverless) + docker (build/push) + Runpod REST (`/run`, `/status`) + Runpod MCP (`stream-worker-logs`, for diagnosis)

## When to use this — the escape hatch

The [development loop](../../skills/runpod-usage/reference/development-loop.md) says
**prefer prebuilt** (Hub worker) then **flash** before building an image. Reach for
this path only when both fall short:

| Situation | Use instead |
| --- | --- |
| A maintained Hub worker does the job | Hub worker (golden path [03](../03-whisper-endpoint/variant-a-hub.md)) |
| Pure-Python handler, standard deps | **flash** (golden path [03](../03-whisper-endpoint/variant-b-flash.md)) |
| **Custom apt/system deps, pinned CUDA/torch, heavy or unusual startup, or you need to debug the model interactively on a GPU before committing to an image** | **this path (09)** |

09 is slower than flash but gives you a **real GPU shell to iterate in** and total
control over the image — the thing you want when something new to serverless is
misbehaving and you need to poke at it live.

## The core idea: one handler, two modes

```
                       MODE_TO_RUN
                            |
        +-------------------+--------------------+
        | pod (default)                          | serverless
        v                                        v
  start.sh: SSH + Jupyter, sleep            start.sh: python handler.py
  you SSH in, run `python handler.py`  -->  runpod.serverless.start({handler})
  → runs handler() ONCE on a sample         → runs handler() PER JOB
        \______________  same handler.py, same module-level model load  ____________/
```

The invariant: the model loads at **import time** (module level — the cold-start
rule), and `handler(event)` is the **same function** both modes call. So whatever
`python handler.py` proves on the pod is what the serverless worker will do. No
"works in dev, breaks in prod" gap.

## The template (vendored in [`template/`](template/))

A trimmed, whisper-flavored version of the base repo. Four files:

| File | Role |
| --- | --- |
| [`handler.py`](template/handler.py) | Loads whisper once at import; `handler(event)` transcribes `audio_url`/`audio_base64`; `pod` mode runs it once on a sample, `serverless` mode hands it to the SDK. |
| [`start.sh`](template/start.sh) | `pod` → SSH + Jupyter + `sleep infinity`; `serverless` → `python handler.py`. |
| [`Dockerfile`](template/Dockerfile) | `ARG BASE_IMAGE` (official `runpod/pytorch`) so torch/CUDA already match hosts; installs `requirements.txt`, copies the two scripts. |
| [`requirements.txt`](template/requirements.txt) | `runpod` + `faster-whisper` (torch comes from the base image — don't reinstall it). |

## Walkthrough — the repeatable loop

### 1. Provision a dev pod (interactive, from an official base)
Create a GPU pod on an official Runpod PyTorch template (or the base repo's
template), register an SSH key first, cost-guard it. Same shape as golden path
[06](../06-dev-pod.md)/[07](../07-network-volume-handoff.md):
```bash
runpodctl pod create --name whisper-dev \
  --template-id runpod-torch-v280 --gpu-id "NVIDIA GeForce RTX 4090" \
  --data-center-ids EU-RO-1 \
  --network-volume-id <vol-id> --volume-mount-path /workspace \  # optional; heavy models -> volume
  --ssh --terminate-after <iso8601 ~2h out>
runpodctl pod get <pod-id>        # poll until it has a runtime (see 06 bad-draw gotcha)
```
ⓥ *pod reaches a runtime and SSH-exec works.*

### 2. Iterate the handler IN the pod (`python handler.py` loop)
SSH in, drop the template into `/app`, and run the pod-mode self-test until it
transcribes. This is the fast inner loop — **no image rebuild per change**:
```bash
ssh -o StrictHostKeyChecking=no -p <port> root@<ip>
cd /app
pip install -r requirements.txt          # write down EVERYTHING you install
python handler.py                         # MODE_TO_RUN defaults to "pod" → runs once on the JFK sample
# → RESULT: {'text': ' And so my fellow Americans...', 'language': 'en', 'duration': 11.0}
```
Edit `handler.py`, re-run, repeat. Each `pip install` / `apt-get install` you needed
**goes into `requirements.txt` / the Dockerfile** — that list is the whole deliverable
of this step.
ⓥ *`python handler.py` prints a correct transcription on the pod.*

### 3. Bake it into an image and build for amd64
Fold your recorded deps into the Dockerfile/requirements, then build **for the
right architecture** (Runpod hosts are x86_64) and push:
```bash
docker build --platform linux/amd64 -t <you>/whisper-dualmode:v1 template/ --push
```
> Pin an explicit tag (`:v1`), never `:latest` (see
> [`../../skills/runpod-usage/reference/docker.md`](../../skills/runpod-usage/reference/docker.md)).
> Swap `--build-arg BASE_IMAGE=...` to change torch/CUDA (matrix in the Dockerfile header).

### 4. Parity check — redeploy the POD from *your* image
Before serverless, run the pod again from the image you just built (still
`MODE_TO_RUN=pod`) and re-run `python handler.py`. This proves the image — not just
your live-patched pod — actually works. Catches "forgot to add a dep to the
Dockerfile" before it becomes a serverless cold-start failure.
ⓥ *the built image transcribes in pod mode with a clean `/app` (no manual patches).*

### 5. Flip to serverless — same image, one env var
Create a serverless endpoint from the same image with `MODE_TO_RUN=serverless`,
scale-to-zero:
```bash
runpodctl serverless create --name whisper-custom \
  --image-name <you>/whisper-dualmode:v1 \
  --gpu-type "NVIDIA GeForce RTX 4090" \
  --workers-min 0 --workers-max 1 \
  --env MODE_TO_RUN=serverless \
  --env MODEL_CACHE_DIR=/runpod-volume/whisper-cache \  # if you attached a volume
  --network-volume-id <vol-id>                          # heavy models -> reuse the download
```
ⓥ *confirm the endpoint's image + env; that `MODE_TO_RUN=serverless` is set.*

### 6. Verify with a real request — "up" ≠ "ready"
Send a **non-empty** input and poll (first call cold-starts; may exceed `runsync`):
```bash
curl -s https://api.runpod.ai/v2/<endpoint-id>/run -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"audio_url":"https://github.com/openai/whisper/raw/main/tests/jfk.flac"}}'
# then poll /status/<job-id> until COMPLETED
```
ⓥ *first (cold) call returns COMPLETED with the same transcription the pod produced —
serverless parity confirmed.*

## Heavy things → network volume (don't bake giant weights)
Small models (whisper `base` ≈ 140 MB) are fine baked in. For **large** weights
(`large-v3`, LLMs, LoRA stacks) don't fatten the image — cache them on a **network
volume** and point the handler at it. That's golden path
[07](../07-network-volume-handoff.md)'s handoff:
- Pod mounts the volume at **`/workspace`**; serverless sees the **same** volume at
  **`/runpod-volume`** (the template's `MODEL_CACHE_DIR` already defaults to
  `/runpod-volume/...` when that path exists).
- Download once (on the pod, or the first worker), reuse across all workers — no
  re-download per cold start.

## Verify it works (what a live run must show — currently spec)
1. `python handler.py` on the pod prints a correct JFK transcription (`en`, ~11 s).
2. The **built image** reproduces that in pod mode on a clean `/app` (step 4).
3. The serverless endpoint returns the **same** transcription for the same audio
   (step 6) — proving pod↔serverless parity.
Green only when #3 passes from outside via a real `/run`.

## Gotchas this path will hit
- **Arch mismatch:** build `--platform linux/amd64` or the worker dies with
  "exec format error" ([docker.md](../../skills/runpod-usage/reference/docker.md), the #1 deploy failure).
- **`:latest` is a trap:** pin explicit tags; Runpod caches images per host and will
  serve a stale `latest`.
- **Load the model at import, not per request** — the whole dual-mode invariant (and
  the cold-start rule) depends on it. Same as the flash "load once" rule.
- **Empty input:** the serverless SDK rejects an empty `{"input":{}}` — send real
  fields (`audio_url`/`audio_base64`). (Same bite as golden paths 07/08.)
- **`MODE_TO_RUN` default is `pod`** — if you forget to set it on the endpoint, the
  worker will start Jupyter and sleep instead of serving. Always set
  `--env MODE_TO_RUN=serverless`.
- **ctranslate2/CUDA:** `faster-whisper` bundles its own CUDA runtime; keep it on an
  official `runpod/pytorch` base to avoid CUDA-version fights. If you see cuDNN/CUDA
  load errors, that's the base-image torch/CUDA not matching — pin via `BASE_IMAGE`.
- **Diagnosis:** if a serverless job times out but the worker looks healthy, pull
  worker logs with the Runpod MCP `stream-worker-logs` before assuming a broken image
  — it's usually a handler/payload bug (lesson from [07](../07-network-volume-handoff.md)).
- **Volume DC pinning:** volume + pod + endpoint must share the data center.

## Cost & cleanup
```bash
runpodctl pod remove <pod-id>              # after you've built the image
runpodctl serverless delete <endpoint-id>  # scale-to-zero (~$0 idle) but delete when done
runpodctl network-volume delete <vol-id>   # if you created one (pod removed first)
```
Pod cost guard: `--terminate-after` at creation (deletes it), not `--stop-after`.

## Relation to the other paths
- **03 (whisper)** is the *easy* whisper: a Hub worker or flash. **Start there.**
- **05 (model → endpoint)** is the docker→endpoint pipeline for a *fixed* model baked
  in. **09 adds the interactive pod dev loop and the dual-mode image** — the thing you
  want while the handler is still changing.
- **07 (volume handoff)** is how 09 serves heavy weights without a fat image.
- Base repo: [justinwlin/Runpod-GPU-And-Serverless-Base](https://github.com/justinwlin/Runpod-GPU-And-Serverless-Base)
  (the full version with more base-image tags and a Jupyter-first pod setup).

## Skill gaps to fold back (after a live run)
- Confirm the exact `runpodctl serverless create` flags for `--env` and image auth
  (public vs private image creds) — update
  [`endpoint-workflows.md`](../../skills/runpod-usage/reference/endpoint-workflows.md).
- Confirm `faster-whisper` on the `runpod/pytorch:2.8.0-cuda12.8` base needs no extra
  CUDA libs; if it does, record the fix in `docker.md`.
