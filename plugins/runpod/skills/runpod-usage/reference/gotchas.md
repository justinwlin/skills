# Common gotchas

Cross-cutting mistakes that bite people deploying on Runpod, as
symptom → cause → fix. See `docker.md` and `storage.md` for the full mechanics.

## Image built for the wrong CPU architecture

- **Symptom:** worker/pod fails to start, "exec format error", or the container
  never comes up — often only after building on an Apple Silicon / ARM machine.
- **Cause:** the image was built for arm64. Runpod hosts are x86_64.
- **Fix:** rebuild with `docker build --platform=linux/amd64 ...` and re-push.
  This is the #1 deploy failure.

## Using the `latest` tag

- **Symptom:** you push new code but workers keep running old behavior; you can't
  tell which version is live.
- **Cause:** `latest` is mutable and Runpod caches images per host, so workers
  serve a stale cached `latest`.
- **Fix:** use explicit tags (`v1.0.0`, `v1.0.1`) or pin the digest
  (`name:tag@sha256:...`). Bump the tag on every change.

## Private image won't pull

- **Symptom:** endpoint/pod stuck initializing; logs show an image pull /
  authentication error.
- **Cause:** the image is private and Runpod has no registry credentials.
- **Fix:** add container-registry credentials in Console → Settings → Container
  Registry, then select them on the template/endpoint. Runpod uses
  `docker login`-style creds.

## Cold starts and timeouts

- **Symptom:** first request after idle is slow or times out; `/runsync` returns
  a timeout while the model is still loading.
- **Cause:** cold start = container pull + start + model load. `runsync` has a
  ~60s ceiling; large model loads can exceed it.
- **Fix:** use `/run` + poll status (or raise the sync timeout); enable FlashBoot;
  keep workers warm with `min_workers` / longer `idle_timeout`; load the model at
  module level, not inside the handler; use cached models or a network volume so
  the model isn't re-downloaded each start.

## Pod shows "Running" but ports/services aren't reachable yet

- **Symptom:** the pod is green/"Running" but the proxy URL 502s, the public IP
  or TCP port mapping is blank, or JupyterLab is a white screen.
- **Cause:** "Running" only means the container exists — services and port
  assignments take extra time to initialize.
- **Fix:** wait ~30–60s; check the **Telemetry** tab to confirm readiness; read
  the assigned public IP / external TCP port from the **Connect** menu once
  populated. Note external TCP port mappings change on every pod reset, and
  Community Cloud public IPs can change on migration/restart.

## Proxy 524 / 100-second timeout

- **Symptom:** requests through `https://<pod-id>-<port>.proxy.runpod.net` die at
  ~100s with a `524`.
- **Cause:** the HTTP proxy runs through Cloudflare, which caps connection time at
  100 seconds.
- **Fix:** don't hold a single request open that long — return a job id and poll,
  use background queues/progress endpoints, or use direct TCP (public IP) instead
  of the proxy for long-lived connections.

## Network volume locked to a data center

- **Symptom:** can't get GPUs, or the endpoint won't schedule workers after
  attaching a volume.
- **Cause:** a network volume lives in one DC; attaching it forces all compute
  into that DC, shrinking GPU availability.
- **Fix:** confirm your target GPU exists in the volume's DC before attaching; or
  attach multiple volumes from different DCs (one per DC) to spread workers —
  remembering data doesn't sync between them automatically.

## Model not baked or mounted

- **Symptom:** handler errors with "model not found," or OOM/download stalls on
  first request.
- **Cause:** the worker has no model — it wasn't baked into the image, cached, or
  mounted from a volume.
- **Fix:** pick one delivery path (bake in, cached HF model at
  `/runpod-volume/huggingface-cache/hub/`, or network volume) and make the handler
  read from that path. For gated/private HF models set `HF_TOKEN`.

## Data disappeared after stop

- **Symptom:** files written during a run are gone after stopping the pod or the
  worker scaling down.
- **Cause:** you wrote to container/ephemeral disk, which is wiped on stop.
- **Fix:** write to `/workspace` (pod volume disk) or a network volume
  (`/runpod-volume` on serverless). Editing/resetting a pod also wipes anything
  outside `/workspace`.

## Huge log or job output

- **Symptom:** logs stop appearing (throttled), or job submission/result is
  rejected for size.
- **Cause:** excessive logging triggers throttling; job payloads exceed limits
  (`/run` ~10 MB, `/runsync` ~20 MB).
- **Fix:** reduce log verbosity / use structured logging; write bulky output to a
  network volume or external S3 and return a URL/reference instead of inlining it.

## GPU out of memory

- **Symptom:** job fails with an OOM/CUDA memory error.
- **Cause:** model or batch size exceeds the selected GPU's VRAM.
- **Fix:** reduce batch size / context length, or pick a larger-VRAM GPU. For
  vLLM, lower `GPU_MEMORY_UTILIZATION` and/or `MAX_MODEL_LEN`.

## Serverless worker "ready" but jobs never run

- **Symptom:** the endpoint has `ready` workers but jobs sit `IN_QUEUE` with
  `inProgress: 0` and never complete.
- **Cause:** a broken/mis-dispatching worker image, or workers `throttled` on a
  scarce GPU pool the model doesn't need.
- **Fix:** switch to a different (maintained) Hub worker on a **broad, high-
  availability GPU pool** — don't wait it out. Diagnose via the endpoint `/health`
  worker counts (there's no first-class serverless worker-log command in runpodctl/
  REST v1; the MCP server does expose `stream-pod-logs`/worker log streaming).
- **Variant — job goes `IN_PROGRESS` then times out:** a worker *picks up* the job
  (`IN_PROGRESS`) but never returns output, and the job fails with
  `"job timed out after 1 retries"` after ~30–50 s. This looks like a broken worker
  but is often a **job-reject by a healthy worker** — get the **worker logs** (MCP
  `stream-worker-logs` or the Console) before assuming the image is bad. A real case
  (flash endpoint, 2026-07-10): the worker's fitness checks passed, then it logged
  `read() got an unexpected keyword argument …` / `Job has missing field(s): id or
  input` — a handler-signature + empty-input bug, **not** a broken worker (see
  flash gotcha "Request body shape"). Only if the logs show a genuinely dead/looping
  worker should you switch workers or try a different data center.

## Delete returns an error but succeeded

- **Symptom:** an MCP `delete-*` (or a DELETE call) returns `isError: true` /
  "Unexpected end of JSON input".
- **Cause:** the Runpod REST API returns **204 No Content**; there's no JSON body
  to parse.
- **Fix:** treat it as success; confirm with a follow-up `get-`/`list-` (the
  resource should 404 / be absent).

## Handler swallowing errors

- **Symptom:** jobs report success but return nothing useful; failures are
  invisible.
- **Cause:** a broad `try/except` suppresses the exception, so the SDK never marks
  the job `FAILED`.
- **Fix:** return a structured error for graceful failures, or re-raise to flag
  the job `FAILED`. Don't silently swallow.
