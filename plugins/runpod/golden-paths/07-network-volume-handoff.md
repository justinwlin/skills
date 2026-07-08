# Golden path 07 — network-volume handoff (pod → volume → serverless)

**Goal:** produce data on a **pod**, persist it to a **network volume**, and have a
**serverless endpoint** read that same data — the pattern behind "fine-tune on a pod,
then serve the adapter from an endpoint."
**Status:** MECHANICS live-verified 2026-07-08 (volume shared pod↔endpoint, mount paths
confirmed). The serverless **read-back did not complete** — the flash reader worker timed
out (reproduced 6×); see [Known blocker](#known-blocker-flash-qb-worker-timeout).
**Lane(s):** runpodctl (volume + pod) + flash (serverless reader)

## When to use this
Any two-phase workflow where a pod produces an artifact and serverless consumes it:
fine-tune → serve the adapter, preprocess a dataset → batch-infer, download/convert a
model once → many endpoint workers reuse it. A network volume is the handoff medium.

## The one thing to get right: same volume, two mount paths

A network volume has **one identity (its ID)** but mounts at a **different path** on each
side (see [`../skills/runpod-usage/reference/storage.md`](../skills/runpod-usage/reference/storage.md)):

| Side | How it attaches | Mount path |
| --- | --- | --- |
| **Pod** | `runpodctl pod create --network-volume-id <id> --volume-mount-path /workspace` | **`/workspace`** (you choose it) |
| **Serverless** | attach the **same** volume id to the endpoint | **`/runpod-volume`** (fixed, not configurable) |

So a pod writing `/workspace/hello.txt` is read by the endpoint at
**`/runpod-volume/hello.txt`** — same bytes, different path. This is the gotcha to watch.
The volume is **pinned to one data center**; the pod AND the endpoint workers must run in
that DC.

## Prerequisites
- `RUNPOD_API_KEY` resolvable (both runpodctl and flash read it).
- `runpodctl` + `flash` installed.

## Walkthrough (verified commands)

### 1. Create the volume
```bash
runpodctl network-volume create --name handoff-demo --size 10 --data-center-id EU-RO-1
# → id, e.g. uov9m8om3w, in EU-RO-1. Pin everything below to this DC.
```

### 2. Pod writes the artifact, then is removed (volume persists)
```bash
runpodctl pod create --name handoff-writer \
  --template-id runpod-torch-v280 --gpu-id "NVIDIA GeForce RTX 4090" \
  --data-center-ids EU-RO-1 \
  --network-volume-id <vol-id> --volume-mount-path /workspace \
  --ssh --terminate-after <iso8601 ~1h out>          # no --ports: nothing to serve

runpodctl pod get <pod-id>                            # poll until it has a runtime
eval "$(runpodctl ssh info <pod-id> | ...)"           # or read ip/port from `ssh info`
ssh -o StrictHostKeyChecking=no -p <port> root@<ip> \
  'echo "handoff ok" > /workspace/hello.txt && cat /workspace/hello.txt'   # verify BEFORE removing

runpodctl pod remove <pod-id>                         # volume (and the file) persist
```
Verified: the file was written and read back on the pod (48 bytes), and after
`pod remove` the volume still listed — data persists independent of the pod.

### 3. Serverless endpoint attaches the SAME volume and reads at `/runpod-volume`
Use **flash** for a code-first reader. Attach the existing volume **by id** (deterministic
— no name matching), pin the same DC:

```python
# main.py
import os
from runpod_flash import Endpoint, DataCenter, NetworkVolume
from runpod_flash.core.resources.cpu import CpuInstanceType

vol = NetworkVolume(id="<vol-id>", datacenter=DataCenter.EU_RO_1)   # attach EXISTING by id

@Endpoint(name="handoff-reader", cpu=CpuInstanceType.CPU3C_1_2,
          workers=(0, 1), datacenter=DataCenter.EU_RO_1, volume=vol)
async def read(input: dict) -> dict:                 # async; param named `input` = plain contract
    p = "/runpod-volume/hello.txt"                   # NOTE: /runpod-volume, not /workspace
    return {"content": open(p).read() if os.path.exists(p) else None}
```
```bash
RUNPOD_API_KEY=... flash deploy
runpodctl serverless list        # confirm the endpoint's networkVolumeId == your volume id
```
Verified: the deployed endpoint reported `networkVolumeId` equal to the volume the pod
wrote to — the **same volume is attached to both sides**. `NetworkVolume(id=...)` attaches
the existing volume deterministically (there is also a `name=`/`dataCenterId=` form).

### 4. Invoke and read the artifact back
```bash
curl -s https://api.runpod.ai/v2/<endpoint-id>/run -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H 'Content-Type: application/json' -d '{"input":{}}'      # then poll /status/<job-id>
```
**This step did not succeed in testing — see the blocker below.**

## Known blocker: flash QB worker timeout
Every invocation of the flash reader returned `"job timed out after 1 retries"` after
~30–50 s with no result — reproduced **6×**: GPU (sync and async handler), CPU, with and
without `dependencies`, and via both raw `curl /run` and the flash SDK client
(`ReadTimeout`). Jobs went `IN_QUEUE → IN_PROGRESS` (a worker picked them up) but the
worker never returned output. That signature — worker runs, job never completes — is the
same class as a broken/mis-dispatching serverless worker (see
[`../skills/runpod-usage/reference/gotchas.md`](../skills/runpod-usage/reference/gotchas.md)).
It was **not** the handoff wiring (the volume attach + paths are correct) or the handler
(trivial file read). Diagnosing it needs **worker logs** — not exposed by `runpodctl`/REST
here; use the Runpod **MCP server** (`stream-*-logs`) or the Console — or try a **different
data center**. Until then, treat the serverless read-back as unverified.

## Cost & cleanup
```bash
runpodctl serverless delete <endpoint-id>        # (flash may create a new endpoint per
runpodctl serverless delete <endpoint-id-2>      #  compute-type change — delete each)
runpodctl network-volume delete <vol-id>         # pod must already be removed
runpodctl serverless list && runpodctl pod list && runpodctl network-volume list   # confirm clean
```
Pod cost guard: `--terminate-after` (deletes the pod), not `--stop-after`. The reader
endpoint is scale-to-zero (`workers=(0,1)`), ~$0 idle.

## Real application (spec): LoRA fine-tune → serve the adapter
The verified simple case scales directly to the motivating workflow:
1. **Train on a pod** onto the volume — golden path
   [`04-finetune-pod.md`](04-finetune-pod.md) writes the adapter to `/workspace/outputs/…`.
2. **Serve from serverless** — a flash/handler endpoint with the **same volume** loads the
   adapter from `/runpod-volume/outputs/…` (the mount-path swap) on top of the base model.

Same three moves as above (volume · pod writes · endpoint reads at `/runpod-volume`) — only
the payload changes from a text file to a trained adapter. Not yet run end to end
(inherits the read-back blocker above).

## Skill facts confirmed / folded back
- `storage.md` already documents the `/workspace` (pod) vs `/runpod-volume` (serverless)
  mount-path split — confirmed correct in practice.
- flash attaches an existing volume via `NetworkVolume(id=...)` (deterministic); the pod
  side uses `--network-volume-id`. Both must be in the volume's DC.
- New gotcha recorded: flash-deployed endpoint jobs timing out with a worker that never
  returns — diagnose via MCP worker logs or a different DC, don't wait it out.
