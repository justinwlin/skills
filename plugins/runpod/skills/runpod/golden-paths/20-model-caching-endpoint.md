# Golden path 20 — serverless endpoint with a host-cached HF model (`--model-reference`)

**Goal:** deploy a serverless LLM endpoint whose weights are **not baked into the image
and not on a network volume** — instead attach a HuggingFace model with
`runpodctl serverless create --model-reference …` so Runpod caches it host-side and the
worker loads it straight from the standard HF cache. Prove it end to end with a **tiny
model** (`Qwen/Qwen2.5-0.5B-Instruct`) so it provisions in seconds and costs a fraction of
a cent, then swap only the model URL for a real one.
**Status:** ⚠️ PARTIALLY VERIFIED — two live runs 2026-07-14 (runpodctl v2.7.1). **Deploy
path confirmed:** `serverless create --hub-id <worker-vllm> --model-reference …:main`
returned an endpoint id with **no baked image and no network volume**, and Runpod resolved
`:main` to a pinned commit — real response:
`"modelReferences":["https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct:7ae557604adf67be50417f59c2c2f167def9a775"]`,
`"gpuIds":"ADA_24"`. **Inference NOT confirmed:** run 1 the worker stayed `initializing`
>20 min (first-ever image pull) and never readied; run 2 it readied in **162s** (image
warm on the pool) but the worker-vLLM engine was extremely slow to serve — a sync
`/openai` call hit a Cloudflare **524** (>100s edge timeout on the first-request model
load), and an async `/run` job then sat `IN_QUEUE` ~15 min behind a "ready" worker
(`inProgress:0` — the "ready but not dispatching" symptom) and was only `running` at
teardown. No `COMPLETED` output was captured, so the on-host cache path is still
unconfirmed. Total spend across both runs ≈ $0.64. Re-run (ideally with worker logs via
MCP/Console) to close it.
**Lane(s):** `runpodctl serverless` (`--model-reference`, **v2.4.0+**) + a vLLM worker
(Hub `--hub-id` or a serverless template) + the OpenAI-compatible invoke route.

## When to use this

| You want… | Use |
| --- | --- |
| A model **already on HuggingFace** served without image bloat or a DC-pinned volume | **HF model cache (this path)** — `--model-reference`, fastest cold starts |
| **Your own** artifact (not on HF) served, managed + versioned | Model Repository — `runpodctl model add` (see [`reference/model-caching.md`](../../runpodctl/reference/model-caching.md)) |
| A **large** model reused across workers where you manage the files | Network volume — golden path [07](07-network-volume-handoff.md) |
| A **fully reproducible** image / system libs baked in | Bake into image — golden path [05](05-model-to-endpoint-pipeline.md) |
| Output from a model **Runpod already hosts**, zero infra | Public Endpoint — golden path [11](11-public-endpoints.md) |

Full comparison of all four delivery methods: [`reference/model-caching.md`](../../runpodctl/reference/model-caching.md).

## Prerequisites
- `RUNPOD_API_KEY` resolvable. Verify: `curl -s -o /dev/null -w '%{http_code}'
  https://rest.runpod.io/v1/endpoints -H "Authorization: Bearer $RUNPOD_API_KEY"` → `200`.
- **runpodctl ≥ v2.4.0** — `--model-reference` does not exist on older builds. Check
  `runpodctl version`; if behind, install from
  [GitHub releases](https://github.com/runpod/runpodctl/releases) (the Homebrew tap can lag).
- Account with credits (a GPU worker bills per second while running).
- A tiny public model needs no HF token. For gated/private models set an `HF_TOKEN`
  endpoint env var.

## Walkthrough

### 1. Confirm the CLI supports the flag
```bash
runpodctl version                       # must be >= 2.4.0
runpodctl serverless create --help | grep -A1 model-reference
```

### 2. Deploy a vLLM endpoint with the cached model
`--model-reference` takes the full HF URL with a `:ref`. Deploy from the Hub vLLM worker
so we don't build an image; attach the tiny model and a small GPU:
```bash
runpodctl serverless create \
  --name gp20-model-cache \
  --hub-id runpod-workers/worker-vllm \
  --gpu-id "NVIDIA GeForce RTX 4090" \
  --model-reference https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct:main
# capture the endpoint id it prints -> <endpoint-id>
```
(Equivalent with a serverless template: `--template-id <id>` instead of `--hub-id`. The
flag is repeatable to attach multiple models. GPU only — no `--compute-type CPU`.)

### 3. Wait until a worker is actually ready
"Created" ≠ "ready". Poll health until a worker is up:
```bash
runpodctl serverless get <endpoint-id>
curl -s "https://api.runpod.ai/v2/<endpoint-id>/health" \
  -H "Authorization: Bearer $RUNPOD_API_KEY"     # workers.ready >= 1
```

### 4. Call it — use the ASYNC route for the first (cold) call
The **synchronous** `/openai/...` and `/runsync` routes are behind a ~100 s edge timeout;
on a cold worker the first-request model load exceeds it and you get a Cloudflare **524**
(observed 2026-07-14). Submit with async `/run` and poll `/status` instead:
```bash
JOB=$(curl -s -X POST "https://api.runpod.ai/v2/<endpoint-id>/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":{"prompt":"Say hello in one word.","sampling_params":{"max_tokens":10,"temperature":0}}}' | jq -r .id)
curl -s "https://api.runpod.ai/v2/<endpoint-id>/status/$JOB" -H "Authorization: Bearer $RUNPOD_API_KEY"
# poll until "COMPLETED"
```
Once a worker is **warm**, the sync OpenAI route is fine for chat:
```bash
curl -s -X POST "https://api.runpod.ai/v2/<endpoint-id>/openai/v1/chat/completions" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen2.5-0.5B-Instruct",
       "messages":[{"role":"user","content":"Say hello in one word."}],
       "max_tokens":10,"temperature":0}'
```

## Verify it works
Results from the 2026-07-14 live run:
1. ✅ `runpodctl version` 2.7.1 and `--model-reference` present in `create --help`.
2. ✅ `serverless create … --model-reference …` returned an endpoint id **without** a baked
   image or a network volume, and resolved `:main` to a pinned commit
   (`…Instruct:7ae557604adf…`) — confirming the model reference was accepted and pinned.
3. ❌ **Not reached:** `/health` never got `workers.ready >= 1` (worker stuck `initializing`
   >20 min; the queued `/openai/v1/chat/completions` request sat `inQueue:1`). Torn down
   before a completion. Re-run and paste a `COMPLETED`/200 chat response here to close this.
4. ⏳ **Cache evidence still open:** the `/runpod-volume/huggingface-cache/hub/` load path is
   Runpod's documented behavior but was **not** independently confirmed on this run (no
   worker ran). Confirm via worker logs or a fast warm-call once a worker is ready.
5. ⏳ Cold/warm latency + spend: pending a successful worker.

## Gotchas to watch
- **v2.3.0 and older don't have `--model-reference`** — the create call will reject the
  flag. Upgrade first (this was the state on the authoring machine).
- **GPU only.** `--model-reference` is rejected with `--compute-type CPU`.
- **The `:ref` matters** — `…Instruct:main` pins the branch/tag/revision; omitting it can
  fail to resolve.
- **Readiness, not fire-and-forget** — a fresh endpoint reports created before any worker
  is ready; poll `/health` before calling (see [15 — monitor & debug](15-monitor-and-debug.md)).
- **First cold start can be very long.** Run 1 (2026-07-14): worker-vLLM sat
  `initializing` >20 min on a fresh RTX 4090 host (first-ever ~10 GB image pull) and never
  readied. Run 2: readied in **162 s** once the image was warm on the pool. Budget
  generously for the first deploy, keep `--workers-min 0` so you don't pay while it churns.
- **Sync routes 524 on cold load.** `/openai/...` and `/runsync` sit behind a ~100 s edge
  timeout; the first-request model load blew past it → Cloudflare **524**. Use async
  `/run` + `/status` for the first call (see step 4).
- **"Ready" ≠ draining the queue.** Run 2: `/health` showed `workers.ready:1` but an async
  `/run` job sat `IN_QUEUE` ~15 min with `inProgress:0`, only reaching `running` at
  teardown — the exact "ready but mis-dispatching" symptom the runpodctl skill flags. If
  jobs don't move behind a ready worker, the worker image is slow/broken to serve; give it
  more time, get worker logs (MCP/Console), or switch workers — don't assume the cache flag
  is at fault (the deploy + ref-pinning worked).

## Cost & cleanup
- A 0.5B model on an RTX 4090 scaled to zero (`--workers-min 0`, the default) bills only
  per request-second — a couple of test calls should be **well under a cent**.
- **Delete the endpoint when done:**
  ```bash
  runpodctl serverless delete <endpoint-id>
  ```

## Skill gaps folded back
- This path exercises `reference/model-caching.md` end to end and is the worked example
  linked from the runpodctl **Serverless → model cache** note and the **Models (Model
  Repository)** section.
- A live run should confirm whether the cached model is visible at
  `/runpod-volume/huggingface-cache/hub/` from inside the worker, closing the one
  unconfirmed mechanic noted in `reference/model-caching.md`.
