# Golden path 10 — high-availability serverless across regions (multi-volume + data sync)

**Goal:** stop a serverless endpoint from being hostage to **one** data center's GPU
supply. A single network volume pins every worker to that volume's DC — when that DC
is scarce or under maintenance, your endpoint can't scale. The fix Runpod supports:
**attach one network volume per DC from several DCs**, so workers spread across
regions. The catch this path exists to teach: **the volumes do not sync
automatically** — you must replicate identical data to every one of them, or workers
in different DCs will serve different data.
**Status:** ⚠️ **spec (document-only, not yet live-verified).** Every mechanism below
is grounded in the official Runpod docs
([network volumes → attach multiple](https://docs.runpod.io/storage/network-volumes),
[S3-compatible API](https://docs.runpod.io/storage/s3-api)) and the verified paths
([03](03-whisper-endpoint/README.md), [05](05-model-to-endpoint-pipeline.md),
[07](07-network-volume-handoff.md)), but the end-to-end multi-region setup hasn't been
run live yet. ⓥ tags mark what a real run should confirm.
**Lane(s):** runpodctl (volumes) + `aws`/S3 API (sync, see [companion-clis](../skills/companion-clis/SKILL.md#aws-cli)) + Console/REST (attach volumes to the endpoint) + optionally a CPU/GPU pod (in-DC population)

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
# Same local source → every per-DC volume. --region + --endpoint-url are per-DC.
for pair in "EU-RO-1:<vol-ro>" "US-KS-2:<vol-ks>" "EUR-IS-1:<vol-is>"; do
  DC=${pair%%:*}; VOL=${pair##*:}
  aws s3 sync ./model-artifacts/ \
    --region "$DC" --endpoint-url "https://s3api-$DC.runpod.io/" \
    "s3://$VOL/model-artifacts/"
done
```
ⓥ *`aws s3 ls` on each volume returns the identical file set + sizes.*

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
ⓥ *files written on the pod appear in the volume after `pod remove`.*

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
runpodctl network-volume create --name ha-ro --size <gb> --data-center-id EU-RO-1
runpodctl network-volume create --name ha-ks --size <gb> --data-center-id US-KS-2
runpodctl network-volume create --name ha-is --size <gb> --data-center-id EUR-IS-1
```
Note: you pay storage **per volume** — N volumes = N× the GB bill. Size only for the
data you replicate.

### 3. Replicate identical data to every volume
Use Method 1/2/3 per DC. **Same source of truth → every volume.** This is the step
that makes or breaks correctness.
ⓥ *`aws s3 ls`/listing is byte-identical (names + sizes, ideally checksums) across all N volumes.*

### 4. Attach all volumes to one endpoint (one per DC)
In the Console: **Serverless → your endpoint → Manage → Edit Endpoint → Advanced →
Network Volumes**, select the volume for **each** DC, Save. (One volume per DC is
enforced.) The endpoint's handler reads its data from `/runpod-volume/...` exactly as
in the single-volume case — workers just now land in multiple DCs.

### 5. Verify HA + parity
Send a burst of requests and confirm (a) workers spin up in **more than one** DC, and
(b) every response is identical regardless of which DC served it — proving the volumes
are in sync. Poll with `/run` + `/status` (cold starts; see
[endpoint-workflows](../skills/runpod-usage/reference/endpoint-workflows.md)).
ⓥ *workers observed across ≥2 DCs; identical output from each; endpoint keeps scaling when one DC is scarce.*

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
- **No auto-sync** — the entire reason this path is hard. Drift → inconsistent responses.
- **One volume per DC** — you can't stack two volumes in the same DC for an endpoint.
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
# Endpoint: detach volumes (Edit Endpoint) or delete the endpoint
runpodctl serverless delete <endpoint-id>
# Delete every volume you created (each billed separately)
runpodctl network-volume delete <vol-ro>
runpodctl network-volume delete <vol-ks>
runpodctl network-volume delete <vol-is>
runpodctl network-volume list      # confirm clean
```
Any sync pods should already be removed with `--terminate-after`.

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
- **Skill gaps to fold back after a live run:** confirm the exact
  `runpodctl`/REST call to attach multiple volumes to an endpoint (docs show the
  Console flow; verify a CLI/API path exists) and update
  [endpoint-workflows.md](../skills/runpod-usage/reference/endpoint-workflows.md). If the
  resumable-transfer step proves essential, consider **vendoring a minimal uploader**
  (just the multipart+resume core) into the skills repo rather than cloning the whole
  tool.
