# Golden path 05 — custom model → serverless endpoint (cross-lane pipeline)

**Goal:** from "serve this custom model as an endpoint", an agent takes a model,
wraps it in a serverless **handler image**, publishes it, deploys an endpoint from
that image, and verifies it with a real request.

This is the **cross-lane** golden path: it chains the **companion CLIs**
(`hf`, `docker`) into the **infra lane** (runpodctl/MCP). It exercises the
ordering rule (**artifacts before infra**) and the credential boundaries a single
lane never hits: an **HF token** (download), a **Docker PAT** (push), and
**registry auth** (Runpod pulling a *private* image). Use it only when no Hub
worker or `flash` handler fits — those are cheaper (see
`../skills/runpod-usage/reference/endpoint-workflows.md` step 1, and golden path 03).

Grounded in: `companion-clis/SKILL.md` (hf / docker / registry),
`docs/serverless/workers/handler-functions.mdx` (handler shape),
`runpodctl/SKILL.md` (template + serverless create, registry), `storage.md`,
`../skills/runpod-usage/reference/development-loop.md`.

## Acceptance criteria

1. **All credentials resolved up front**, each at its own boundary:
   `RUNPOD_API_KEY` (infra), `HF_TOKEN` (download, if gated/private),
   Docker Hub **PAT** (`docker login`), and — if the image is **private** —
   Runpod **registry auth** so workers can pull it. Missing any → escalate.
2. **Ordering: artifacts before infra.** The image must be **built and pushed**
   before the endpoint is created — an endpoint references an image by tag, so it
   can't be created against an image that doesn't exist yet.
3. Handler wraps the model in the Runpod contract: `runpod.serverless.start({"handler": handler})`, reading `job["input"]`, returning JSON.
4. Image built **`--platform=linux/amd64`** (Runpod runs x86 Linux) with an
   explicit **semver tag** (never `latest`), pushed to Docker Hub.
5. Endpoint created from that image (`--workers-min 0`, scale-to-zero), then
   **verified with a real request** — first call cold-starts, so `/run` + poll
   `/status`, then `/runsync` once warm.

## Lane handoffs (who does what, in order)

```
companion (hf)      →  companion (docker)        →  infra (runpodctl)         →  invoke
download the model     build amd64 + push image     registry auth (if private)   /run → poll
(HF_TOKEN)             (Docker PAT)                  template + endpoint          /status → /runsync
                                                     (RUNPOD_API_KEY)
        └────────── artifacts exist ──────────┘  └────────── infra points at them ─────────┘
```

The handoff point is the **image tag**: everything left of it produces
`myorg/my-model-worker:v1.0.0`; everything right of it consumes that exact tag.

## Ideal agentic flow

```bash
# 0. Credentials — resolve every boundary before doing work
export RUNPOD_API_KEY=your_key
export HF_TOKEN=hf_...                       # only if the model is gated/private
docker login -u <dockerhub-user>             # paste the Docker Hub PAT (not password)

# 1. ARTIFACT: fetch the model (companion: hf). Filter to the weights you need.
hf download <org>/<model> --include "*.safetensors" "*.json" \
  --local-dir ./model                        # baked into the image below

# 2. ARTIFACT: handler + Dockerfile (Runpod contract)
cat > handler.py <<'PY'
import runpod
# load the model ONCE at import (cold start), reuse across calls
def handler(job):
    data = job["input"]                      # {"input": {...}} contract
    # ... run inference on ./model, return JSON ...
    return {"result": "..."}
runpod.serverless.start({"handler": handler})
PY
cat > Dockerfile <<'DOCKER'
FROM runpod/base:0.6.2-cuda12.4.1            # or a pytorch base; pin the tag
COPY model/ /model/
COPY handler.py /handler.py
RUN pip install runpod                       # + your model deps
CMD ["python", "-u", "/handler.py"]
DOCKER

# 3. ARTIFACT: build for amd64 with an explicit tag, then push (companion: docker)
docker build --platform=linux/amd64 -t <dockerhub-user>/my-model-worker:v1.0.0 .
docker push <dockerhub-user>/my-model-worker:v1.0.0

# 4. INFRA: if the image is PRIVATE, register registry auth so Runpod can pull it
runpodctl registry create --name dockerhub \
  --username <dockerhub-user> --password <docker-PAT>     # skip for a public image

# 5. INFRA: create a serverless template from the image, then the endpoint
runpodctl template create --name my-model-tpl --serverless \
  --image <dockerhub-user>/my-model-worker:v1.0.0          # attach registry cred in Console for a private image
runpodctl serverless create --template-id <template-id> \
  --name my-model --gpu-id "NVIDIA GeForce RTX 4090" \
  --workers-min 0 --workers-max 3            # scale-to-zero

# 6. VERIFY with a real request — first call cold-starts (image pull + model load)
EP=<endpoint-id>
JOB=$(curl -s https://api.runpod.ai/v2/$EP/run -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" -d '{"input":{"prompt":"hello"}}' | jq -r .id)
until curl -s https://api.runpod.ai/v2/$EP/status/$JOB \
  -H "Authorization: Bearer $RUNPOD_API_KEY" | jq -e '.status=="COMPLETED"'; do sleep 5; done
# then, once warm, /runsync is fine:
curl -s https://api.runpod.ai/v2/$EP/runsync -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" -d '{"input":{"prompt":"hello"}}'
```

## Runpod gotchas this path must respect

- **`--platform=linux/amd64` always.** Building on an Apple-Silicon/arm host
  without this flag produces an arm image that fails to start on Runpod's x86
  workers (`companion-clis/SKILL.md`).
- **Never `latest`.** `latest` doesn't track your newest push — pin a semver tag
  or workers may silently pull a stale build. Bump the tag on every change.
- **Private image ⇒ registry auth.** A private Docker Hub image won't pull unless
  Runpod has credentials: register `docker login`-type auth
  (`runpodctl registry create`, or Console → Container Registry Settings) and
  attach it to the template. A public image needs none. Runpod currently supports
  only `docker login`-type registry credentials.
- **Artifacts before infra (the ordering rule).** Push the image *before*
  `serverless create`; the endpoint only references the tag. Creating the endpoint
  first just gives you workers that can't pull.
- **Cold start is real.** First request pulls the (often multi-GB) image and loads
  the model — it can exceed `runsync`'s ~60s window. Use `/run` + poll `/status`
  for the first call, then `/runsync` once warm (`endpoint-workflows.md`).
- **Payload limits.** `/run` ~10 MB, `/runsync` ~20 MB — pass large inputs/outputs
  as URLs (or a network volume), not inline bytes (`storage.md`, `networking.md`).
- **Big model? Don't always bake.** Baking a huge model bloats the image and slows
  every cold start. For a public/gated HF model, prefer Runpod's **cached model**
  (`--model-reference` on `serverless create`) or a **network volume** over `COPY`
  (`storage.md`). Baking is best for small/private models.
- **Cheaper lanes first.** A maintained **Hub worker** (zero code) or a **flash**
  handler (no Docker/registry at all) beats this pipeline when one fits — this
  custom-image path is the last resort (golden path 03; `endpoint-workflows.md`).

## Status: SPEC (not yet live-verified)

Unlike golden paths 01–03 (live-verified), this path has **not** been run end to
end. The lane handoffs, credential boundaries, and gotchas are grounded in
`companion-clis/SKILL.md`, `runpodctl/SKILL.md`, and the handler docs, but the
exact base-image tag, the `template create --serverless` → `serverless create
--template-id` two-step (vs a single `serverless create --image`, if it exists),
and how a private-image registry credential attaches at create time (CLI flag vs
Console) should be confirmed live before this is marked covered — see gaps below.
