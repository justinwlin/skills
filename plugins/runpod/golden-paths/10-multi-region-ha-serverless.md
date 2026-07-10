# Golden path 10 — high-availability serverless across regions (multi-volume + data sync)

**Goal:** stop a serverless endpoint from being hostage to **one** data center's GPU
supply. A single network volume pins every worker to that volume's DC — when that DC
is scarce or under maintenance, your endpoint can't scale. The fix Runpod supports:
**attach one network volume per DC from several DCs**, so workers spread across
regions. The catch this path exists to teach: **the volumes do not sync
automatically** — you must replicate identical data to every one of them, or workers
in different DCs will serve different data.
**Status:** ✅ **COVERED — live-verified 2026-07-10** end to end. Created **two** 10 GB
volumes (ha-a in **EU-RO-1**, ha-b in **EU-CZ-1**), **S3-synced identical data to both**
(`aws s3 ls` byte-identical), deployed **one** endpoint attached to **both** volumes, and
sent a 16-request burst: **16/16 `COMPLETED`, served by 3 workers across both DCs**
(EU-RO-1 ×2, EU-CZ-1 ×1), each worker reading its **co-located** volume, and **every
response identical** (one distinct marker + data string across all 16). The one real
correction a live run forced: **the headless multi-volume attach is neither
`runpodctl --network-volume-ids` nor REST `networkVolumeIds[]` — both pass bare strings
and the API rejects them; it takes a GraphQL `saveEndpoint` with
`networkVolumeIds: [{networkVolumeId}]` objects** (see step 4). Scope note: **Methods 2/3
(pod-based population) were *not* re-run here** — they're already live-proven by golden
path [07](07-network-volume-handoff.md) (a pod writing to a mounted volume). This path's
live proof is the **S3-API sync + multi-volume attach + multi-DC verification**.
**Lane(s):** runpodctl (volumes) + `aws`/S3 API (sync, see [companion-clis](../skills/companion-clis/SKILL.md#aws-cli)) + **GraphQL `saveEndpoint`** (attach multiple volumes — the headless path; Console also works) + optionally a CPU/GPU pod (in-DC population, per [07](07-network-volume-handoff.md))

## The problem, precisely

| Volumes attached | Where workers can schedule | Availability |
| --- | --- | --- |
| **One** volume | **only** that volume's DC | hostage to one DC's GPU pool + maintenance windows |
| **Multiple** volumes (one per DC, N DCs) | **any** of those N DCs | N× the GPU pools to draw from; survives one DC going scarce/down |

Runpod's rule (from the docs): with multiple volumes attached, **workers are
distributed across those DCs, each worker getting exactly one volume based on its
assigned location**, and **you can attach at most one volume per DC**.

## The catch: no automatic sync (this is the whole job)

> **Data does not sync automatically between volumes.** Each per-DC volume is an
> independent disk. A worker in EU-RO-1 reads the EU-RO-1 volume; a worker in US-KS-2
> reads the US-KS-2 volume. If those two disks differ, the *same endpoint* returns
> *different behavior* depending on which DC a request lands in — a silent, confusing
> bug.

So HA serverless = **(multi-volume attach) + (a discipline that keeps every volume
byte-identical)**. The rest of this path is about that second half: getting the same
data onto every volume, and keeping it there.

## Three ways to populate / sync each per-DC volume

You need a "writer" with access to each DC's volume. Pick the cheapest that can do the
job; escalate only when it can't.

| Method | Compute cost | Use when | How |
| --- | --- | --- | --- |
| **S3-compatible API** (recommended) | **none** — no pod at all | the DC supports the S3 API and the data is files you already have (models, datasets, adapters) | `aws s3 sync`/`cp` or boto3 against the DC's S3 endpoint; or the community CLI for resumable large transfers |
| **CPU pod** | cheap (~$/hr CPU) | the DC has no S3 API, or you must **generate/unpack/process** data in-DC, or you're copying **volume→volume** | mount the volume at `/workspace` on a CPU pod in that DC; download/build there, or `runpodctl send`/`receive` between two pods |
| **Cheapest GPU pod** | most expensive | you need a **GPU to produce** the artifact in that DC (build a TensorRT engine, quantize, warm a GPU-specific cache) | same as CPU pod but with a small GPU; do the GPU work, write to `/workspace`, remove the pod |

### Method 1 — S3 API (no compute, the default)

The S3-compatible API writes straight to a volume with **no pod running** — cheapest
and fastest for file data. Full setup (S3 API keys, `aws configure`, endpoints,
path mapping) is in [companion-clis → AWS CLI](../skills/companion-clis/SKILL.md#aws-cli).

> **Manual step — S3 API keys are Console-only.** They cannot be created via
> `runpodctl` or any REST/GraphQL call — only in the Console (Settings → S3 API Keys →
> Create). The access key is your Runpod **user id** (`user_...`), the secret is shown
> **once** (`rps_...`). An agent must **escalate** for these if they aren't already in
> `~/.aws/credentials` / env vars — it can't self-provision them. If S3 keys aren't
> available, use the CPU-pod method below (no S3 keys needed).
Each DC has its own endpoint (`https://s3api-<DC>.runpod.io/`); the **bucket name is
the volume id**. Sync the *same source directory* to *each* volume:

```bash
# Same local source → every per-DC volume. --region is the DC id; the endpoint host is
# the DC id lower-cased (DNS is case-insensitive, so upper-case also resolves).
for pair in "EU-RO-1:d4qw56wbx9" "EU-CZ-1:xeb2u0ejfo"; do   # DC:volume-id
  DC=${pair%%:*}; VOL=${pair##*:}
  aws s3 sync ./ha-data/ \
    --region "$DC" \
    --endpoint-url "https://s3api-$(echo "$DC" | tr 'A-Z' 'a-z').runpod.io/" \
    "s3://$VOL/ha-data/"
done
```
✅ **Live 2026-07-10** — `aws s3 ls` on *both* volumes returned the identical file set +
sizes (the whole point — proves the two independent disks now match):
```
$ aws s3 ls --region EU-RO-1 --endpoint-url https://s3api-eu-ro-1.runpod.io/ s3://d4qw56wbx9/ha-data/
2026-07-10 17:22:30         77 data.txt
2026-07-10 17:22:30         28 marker.txt
$ aws s3 ls --region EU-CZ-1 --endpoint-url https://s3api-eu-cz-1.runpod.io/ s3://xeb2u0ejfo/ha-data/
2026-07-10 17:22:31         77 data.txt
2026-07-10 17:22:31         28 marker.txt
```
> A preconfigured `aws` profile (`--profile runpod`) held the S3 creds (access key =
> Runpod `user_...`, secret = `rps_...`); those keys are still **Console-only** to create.

- **Large files / flaky links:** `aws s3 sync` is fine for modest trees but **struggles
  past ~10,000 files** and has weak resume. For big weights, prefer the community tool
  (resumable multipart, auto chunk sizing, MD5-verified resume) — see
  [Companion tool](#companion-tool-resumable-transfers). Bump retries on 502s:
  `export AWS_RETRY_MODE=standard AWS_MAX_ATTEMPTS=10`.
- **S3 API is DC-limited:** only [select DCs](https://docs.runpod.io/storage/s3-api#datacenter-availability)
  expose it (EU-RO-1, EU-CZ-1, EUR-IS-1, US-KS-2, and more). For a DC without S3, use
  Method 2.

### Method 2 — CPU pod (in-DC, no GPU)

When a target DC lacks S3, or you need to unpack/build in-DC, or you're moving data
volume→volume: bring up a **cheap CPU pod** in that DC with the volume mounted at
`/workspace` (golden path [07](07-network-volume-handoff.md) is the exact pod+volume
pattern), do the work, then remove the pod (the volume persists):

```bash
runpodctl pod create --name sync-cpu \
  --data-center-ids <dc> \
  --network-volume-id <vol-in-that-dc> --volume-mount-path /workspace \
  --ssh --terminate-after <iso8601 ~1h out>          # a CPU flavor; no GPU needed
# SSH in, populate /workspace (hf download, curl, tar -x, aws s3 cp from your own bucket, …)
runpodctl pod remove <pod-id>                          # volume keeps the data
```
Volume→volume copy: mount **both** volumes on two pods and use `runpodctl send` /
`receive` (docs: *Migrate files between volumes*).
> *Pod-writes-to-volume is already live-proven by golden path
> [07](07-network-volume-handoff.md) — not re-run here; this path's live proof is the S3
> route below.*

### Method 3 — cheapest GPU pod (in-DC, GPU work)

Same as Method 2 but with a small GPU, only when the artifact must be produced on a
GPU **in that DC** (e.g. build a TensorRT/engine file, quantize weights, prime a
GPU-specific cache). It's the priciest writer — reach for it last. Use the cheapest
GPU available in that DC and `--terminate-after`.

## Walkthrough — stand up the HA endpoint

### 1. Pick the DCs
Choose N DCs that (a) have your target GPU in good supply and (b) ideally expose the
S3 API (cheapest sync). Confirm the GPU exists in each DC before committing — a volume
in a DC where your GPU is unavailable adds **zero** availability (workers there can't
schedule).

### 2. Create one volume per DC
```bash
runpodctl network-volume create --name ha-a --size 10 --data-center-id EU-RO-1
runpodctl network-volume create --name ha-b --size 10 --data-center-id EU-CZ-1
```
✅ Live output (each returns its id — these become the S3 bucket names and the attach args):
```json
{ "dataCenterId": "EU-RO-1", "id": "d4qw56wbx9", "name": "ha-a", "size": 10 }
{ "dataCenterId": "EU-CZ-1", "id": "xeb2u0ejfo", "name": "ha-b", "size": 10 }
```
Note: you pay storage **per volume** — N volumes = N× the GB bill. Size only for the
data you replicate. Flags are exactly `--name`, `--size` (1-4000 GB), `--data-center-id`
(all required; no other options).

### 3. Replicate identical data to every volume
Use Method 1/2/3 per DC. **Same source of truth → every volume.** This is the step
that makes or breaks correctness. Here: a tiny `ha-data/` (a `marker.txt` + `data.txt`)
`aws s3 sync`'d to **both** buckets (step "Method 1" above), then `aws s3 ls` confirmed
the two volumes were byte-identical (77 B + 28 B on each). ✅

### 4. Attach all volumes to one endpoint (one per DC)
You need a **template** first (`runpodctl serverless create` takes `--template-id`/`--hub-id`,
never `--image` — same two-step as golden path [05](05-model-to-endpoint-pipeline.md)):
```bash
runpodctl template create --name rp-gp10-tpl --serverless \
  --image justinrunpod/rp-gp10:v1 --container-disk-in-gb 10   # → template id p8b3v1prf1
```
**The headless multi-volume attach is the one thing the docs got wrong for the CLI/REST
layer.** Both documented "list" inputs are **broken** — they send bare strings, but the
GraphQL layer wants `NetworkVolumeIdsInput` **objects** (`{ networkVolumeId }`):
```bash
# ✗ runpodctl — rejected:
runpodctl serverless create --template-id p8b3v1prf1 --compute-type CPU \
  --network-volume-ids d4qw56wbx9,xeb2u0ejfo ...
#   → graphql: ... "d4qw56wbx9" at input.networkVolumeIds[0]; Expected type
#     "NetworkVolumeIdsInput" to be an object.
# ✗ REST POST /v1/endpoints with "networkVolumeIds": ["d4qw56wbx9","xeb2u0ejfo"] — same error.
```
The Console flow works (**Serverless → Edit Endpoint → Advanced → Network Volumes**,
one per DC, Save). The **headless** path that works is a two-step: create the endpoint
with a single volume, then attach the full set via the GraphQL `saveEndpoint` mutation
with the object form:
```bash
# a) create with ONE volume (REST accepts the singular field)
curl -s -X POST https://rest.runpod.io/v1/endpoints \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d '{"templateId":"p8b3v1prf1","name":"rp-gp10-ha","computeType":"CPU",
       "networkVolumeId":"d4qw56wbx9","dataCenterIds":["EU-RO-1","EU-CZ-1"],
       "workersMin":0,"workersMax":4}'          # → endpoint id koh9bjdv1v98im

# b) attach BOTH via GraphQL saveEndpoint (objects, not strings).
#    NOTE the User-Agent header — api.runpod.io returns 403/1010 (Cloudflare) without a browser-ish UA.
curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  -H 'Content-Type: application/json' -H 'User-Agent: Mozilla/5.0' \
  -d '{"query":"mutation($input:EndpointInput!){saveEndpoint(input:$input){id name}}",
       "variables":{"input":{"id":"koh9bjdv1v98im","name":"rp-gp10-ha","templateId":"p8b3v1prf1",
         "dataCenterIds":["EU-RO-1","EU-CZ-1"],
         "networkVolumeIds":[{"networkVolumeId":"d4qw56wbx9"},{"networkVolumeId":"xeb2u0ejfo"}],
         "workersMin":0,"workersMax":4,"scalerType":"QUEUE_DELAY","scalerValue":1,"idleTimeout":10}}}'
```
✅ `GET /v1/endpoints/koh9bjdv1v98im` then confirmed `"networkVolumeIds":["d4qw56wbx9","xeb2u0ejfo"]`.
The handler reads its data from `/runpod-volume/...` exactly as in the single-volume case.
> **Caveat (honest):** `computeType` lives only in the REST layer, **not** in GraphQL
> `EndpointInput`. The GraphQL `saveEndpoint` round-trip in (b) reset the endpoint to the
> GPU default, so the live workers ran on **GPU** (RTX A4500 in EU-RO-1, RTX 3090 in
> EU-CZ-1) even though (a) asked for CPU. A pure-CPU headless multi-volume path would need
> the CPU flavor passed *through GraphQL* (`instanceIds`/`cpuFlavorIds`) — not yet verified.
> The HA behavior (multi-DC, per-DC volume, parity) is identical either way.

### 5. Verify HA + parity — ✅ live 2026-07-10
Burst of **16** `/run` jobs, polled to completion (cold start ~10 s queue, ~135 ms exec):
```
STATUS:            {'COMPLETED': 16}          # 16/16 succeeded
WORKERS (3 total): EU-RO-1 ×2, EU-CZ-1 ×1     # scheduled across BOTH DCs
DISTINCT markers:  1   ('golden-path-10 HA marker v1')     # identical regardless of DC
DISTINCT data:     1   ('shared-model-payload: checksum-anchor 42 …')
```
Per-worker identity (from the handler returning `socket.gethostname()` + `RUNPOD_*` env):
```
worker 4100bc76ce48: RUNPOD_DC_ID=EU-CZ-1  RUNPOD_VOLUME_ID=xeb2u0ejfo  (ha-b)
worker ca7909f9bdbe: RUNPOD_DC_ID=EU-RO-1  RUNPOD_VOLUME_ID=d4qw56wbx9  (ha-a)
worker b1b4e4d2f0f2: RUNPOD_DC_ID=EU-RO-1  RUNPOD_VOLUME_ID=d4qw56wbx9  (ha-a)
```
This is the whole thesis, proven: **each worker landed in a different DC and mounted
that DC's own volume** (`RUNPOD_VOLUME_ID` = the co-located volume, `/runpod-volume`
points at it), yet **every response was byte-identical** because both volumes carried the
same synced data. `RUNPOD_DC_ID` is the clean per-request DC identifier; poll with
`/run` + `/status` (see [endpoint-workflows](../skills/runpod-usage/reference/endpoint-workflows.md)).

## Keeping volumes in sync (operating discipline)
- **One source of truth.** Treat a canonical local dir (or your own S3 bucket) as
  authoritative; push it to every Runpod volume. Never edit volumes ad hoc.
- **Re-sync on every data change**, to **all** volumes, before it goes live. A model
  bump that lands on 2 of 3 volumes = 1/3 of traffic serving the old model.
- **Verify after sync** — compare listings/sizes (checksums if you can) across volumes.
- **Don't write from workers.** Concurrent writes from multiple workers to a volume can
  corrupt it (docs warning). Volumes here are **read-only data planes**; writes go
  through your sync pipeline, not the handler.

## Gotchas
- **Multi-volume attach is GraphQL-only (headless).** `runpodctl --network-volume-ids a,b`
  and REST `POST /v1/endpoints {"networkVolumeIds":["a","b"]}` **both fail** — they pass
  bare strings, but the API wants `NetworkVolumeIdsInput` objects. Verified working path:
  create with a single volume, then `saveEndpoint(networkVolumeIds:[{networkVolumeId:…}])`
  (step 4). The Console UI also works. *`--network-volume-id` (singular) on `runpodctl` /
  `networkVolumeId` on REST attach exactly one volume and are fine.*
- **`api.runpod.io/graphql` needs a browser-ish `User-Agent`** — without one, Cloudflare
  returns `403 / error 1010`. Any non-empty `User-Agent: Mozilla/5.0` clears it.
- **`computeType` is REST-only, not in GraphQL `EndpointInput`.** A `saveEndpoint`
  round-trip resets an endpoint to the GPU default; the live run landed on GPU workers
  despite requesting CPU. HA behavior is unaffected, but don't expect CPU pricing after a
  GraphQL edit unless you re-pin the CPU flavor through GraphQL.
- **No auto-sync** — the entire reason this path is hard. Drift → inconsistent responses.
- **One volume per DC** — you can't stack two volumes in the same DC for an endpoint.
  (Live: each worker's `RUNPOD_VOLUME_ID` = its own DC's volume.)
- **S3 API isn't in every DC** — check availability; fall back to a CPU pod (Method 2).
- **GPU must exist in each chosen DC** — a volume in a GPU-dry DC adds no availability.
- **`aws s3 sync` scaling** — flaky past ~10k files; `ls` slow on >10k files / >10GB;
  use the resumable tool for big trees, and `AWS_MAX_ATTEMPTS=10` on 502s.
- **Cost scales with N** — storage billed per volume ($0.07/GB/mo to 1TB, then $0.05).
- **Access key gotcha** — for the S3 API the AWS "access key" is your Runpod **user
  id** (`user_...`), the secret is the S3 key (`rps_...`) — not your `RUNPOD_API_KEY`
  ([companion-clis](../skills/companion-clis/SKILL.md#aws-cli)).

## Cost & cleanup
```bash
runpodctl serverless delete koh9bjdv1v98im     # the endpoint (deletes the multi-volume attach)
runpodctl template delete   p8b3v1prf1         # the template
runpodctl network-volume delete d4qw56wbx9     # ha-a (EU-RO-1) — billed separately
runpodctl network-volume delete xeb2u0ejfo     # ha-b (EU-CZ-1)
runpodctl serverless list && runpodctl network-volume list && runpodctl pod list   # confirm clean
```
✅ All four `{"deleted": true}` on the live run; lists came back with only pre-existing
resources. Any sync pods should already be removed with `--terminate-after`. The pushed
image `justinrunpod/rp-gp10:v1` (a ~150 MB `python:3.11-slim` + `runpod` SDK handler that
returns `/runpod-volume` contents plus `RUNPOD_DC_ID`/`RUNPOD_VOLUME_ID`) was **left
public** so this doc references a real, pullable tag; it costs nothing.

## Companion tool: resumable transfers
For large weights across several volumes, `aws s3 sync` (weak resume, 10k-file wall) is
the pain point. The community **[Runpod Network Volume Storage
Tool](https://github.com/justinwlin/Runpod-Network-Volume-Storage-Tool)** wraps the
same S3 API with **resumable multipart uploads** (auto chunk sizing, MD5-verified
resume), directory sync with excludes, an interactive browser, a Python SDK, and a
REST server. It's already in the official docs
([community solutions](https://docs.runpod.io/community-solutions/runpod-network-volume-storage-tool)).
```bash
git clone https://github.com/justinwlin/Runpod-Network-Volume-Storage-Tool.git
cd Runpod-Network-Volume-Storage-Tool && uv sync
export RUNPOD_API_KEY=... RUNPOD_S3_ACCESS_KEY=user_... RUNPOD_S3_SECRET_KEY=rps_...
uv run runpod-storage upload ./model-artifacts <vol-id>   # resumable; re-run to resume
```
> Registered in [companion-clis → optional: resumable volume transfers](../skills/companion-clis/SKILL.md#optional-resumable-volume-transfers-community-tool).

## Relation to other paths & skill gaps
- **07 (network-volume handoff)** is the single-volume pod↔serverless case; **10 scales
  it to N volumes across DCs** for availability.
- **05/09** produce the artifact you then replicate here.
- **Skill gap RESOLVED (live 2026-07-10):** the headless multi-volume attach is **not**
  `runpodctl --network-volume-ids` and **not** REST `networkVolumeIds[]` (both send bare
  strings → `NetworkVolumeIdsInput` object-type error). The working call is the GraphQL
  `saveEndpoint` mutation with `networkVolumeIds: [{networkVolumeId: "<id>"}, …]` (create
  with a single volume via REST/`runpodctl` first, then attach the full set) — plus a
  `User-Agent` header to clear Cloudflare on `api.runpod.io`. This should be folded into
  [endpoint-workflows.md](../skills/runpod-usage/reference/endpoint-workflows.md) as the
  canonical multi-region attach recipe, and a `runpodctl`-side bug report is warranted
  (`--network-volume-ids` advertises the feature but emits the wrong GraphQL shape).
- **Still open:** a pure-**CPU** headless multi-volume endpoint — `computeType` isn't a
  GraphQL field, so the `saveEndpoint` attach reverts to GPU; needs the CPU flavor passed
  via GraphQL (`instanceIds`/`cpuFlavorIds`). If the resumable-transfer step proves
  essential, consider **vendoring a minimal uploader** (just the multipart+resume core)
  into the skills repo rather than cloning the whole tool.
