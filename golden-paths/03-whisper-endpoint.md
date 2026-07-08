# Golden path 03 — Whisper endpoint (URL → text)

**Goal:** deploy a serverless endpoint that, given an audio URL (or base64 audio),
returns the transcription. This is a **serverless** path (request/response,
scale-to-zero), not a pod.

Status: **COVERED** — live-verified 2026-07-07. Route chosen: **runpodctl + Runpod Hub**.

## Lane choice (and why)

Whisper is a request/response inference API → **serverless**, and the least-fragile
way to stand up a *known* worker is the **Runpod Hub**, deployed with **runpodctl**
(the router: "Deploy from the Hub → runpodctl; MCP has no Hub tools"). A ready Hub
worker means no handler code, no `docker build --platform=linux/amd64`, no registry
auth, no cloudpickle/import gotchas — just `serverless create --hub-id …`.

Rejected:
- **flash** — great for *custom/small* code-first handlers you iterate on, but for a
  heavy, prebuilt model you'd be re-implementing a faster-whisper handler that the
  Hub already ships and maintains. More moving parts, no upside here.
- **Custom image + endpoint** — most fragile (write handler → build amd64 → push →
  maybe registry auth → create endpoint). Only worth it if no good Hub worker exists.

## Variant A — Runpod Hub worker (recommended)

The least-fragile path: deploy a maintained Hub worker with runpodctl. No handler
code, no image build. (Prefer a from-scratch code handler you own? See
[Variant B — flash](#variant-b--build-from-scratch-with-flash).)

### Pick the worker (this matters — not all Hub workers work)

`runpodctl hub search whisper --type SERVERLESS`. There is **no** official
`runpod-workers/worker-faster_whisper` in the Hub; the dedicated transcription
workers are community WhisperX images. Two were tried:

| Worker | hub-id | GPU pool | Result |
| --- | --- | --- | --- |
| `hapnan/whisperx-worker` v1.0.6 | `cmh98s0m8000002jpc7gz8v0i` | pinned `ADA_48_PRO` | **Failed** — workers reported `ready` but never consumed the queue (in-progress stuck at 0 for >8 min); pool also threw `throttled` workers. Deleted. |
| **`kodxana/whisperx-worker_v2` v1.0.7** | **`cmpo4s6ma000008jl2x6y49hh`** | `AMPERE_16,AMPERE_24,ADA_24` | **Works** — first job COMPLETED in ~27s total (18s cold-start delay + 9s exec). Chosen. |

Lesson: prefer the actively-maintained worker on a **broad, high-availability GPU
pool** (16–24 GB tiers) over one pinned to a scarce 48 GB tier. WhisperX large-v2
only needs ~10 GB VRAM, so pinning `ADA_48_PRO` bought nothing and cost availability.
When a Hub worker's workers go `ready` but jobs sit `IN_QUEUE` with `inProgress: 0`,
that worker image is broken/mis-dispatching — switch workers, don't wait it out.

### Deploy

```bash
export RUNPOD_API_KEY=...   # https://runpod.io/console/user/settings
runpodctl serverless create \
  --hub-id cmpo4s6ma000008jl2x6y49hh \
  --name whisperx-v2 \
  --workers-min 0 --workers-max 3        # min 0 = scale-to-zero, ~0 idle cost
```

Returns an endpoint id (this run: `tlftkn7v2ixdw0`). The Hub config supplies the
GPU pool, container disk, and CUDA version automatically.

### Input schema

`POST` body is `{"input": { ... }}`. Key fields:

| Field | Type | Req | Notes |
| --- | --- | --- | --- |
| `audio_file` | string | yes | **HTTP(S) URL** to the audio, **or base64-encoded audio** (optionally a `data:audio/wav;base64,…` data-URI prefix). Both verified. |
| `language` | string | no | ISO code (`en`, `fr`, …); auto-detected if omitted |
| `align_output` | bool | no | word-level timestamps (default false) |
| `diarization` | bool | no | speaker labels; needs `HF_TOKEN` env / `huggingface_access_token` |
| `batch_size` | int | no | default 64 |
| `initial_prompt`, `temperature`, `vad_onset`, `vad_offset`, `min_speakers`, `max_speakers` | — | no | see worker README |

**Output:** `{"output": {"detected_language": "en", "segments": [{"start","end","text", ...}]}}`.
The transcript is the concatenation of `segments[].text`.

**"Uploading" audio:** there is no file-upload step. Either (a) host the file at a
public URL and pass it as `audio_file`, or (b) base64-encode the bytes and pass the
string as `audio_file`. Base64 rides the job payload, so respect the limits: `/run`
~10 MB, `/runsync` ~20 MB. For larger files, use a URL (presigned S3/GCS works).

### Verify (tested)

```bash
curl -s https://api.runpod.ai/v2/<endpoint-id>/runsync \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":{"audio_file":"https://github.com/runpod-workers/sample-inputs/raw/main/audio/gettysburg.wav"}}'
```

Returned (warm: 127 ms delay + 4.7 s exec):

```
Four score and seven years ago, our fathers brought forth on this continent a new
nation, conceived in liberty and dedicated to the proposition that all men are
created equal.
```

Note: first request cold-starts (image pull + model load) ~20–90 s, which can exceed
`runsync`'s 60 s sync window — use `/run` + poll `/status/<id>` for the first call,
then `runsync` once warm. Bound any poll loop.

## Variant B — build from scratch with flash

Also live-verified 2026-07-07. When you want a **custom/lighter** worker than any
Hub image (own model size, own I/O schema, pre/post-processing), build it code-first
with **flash**. Verified end to end: a hand-written faster-whisper handler,
`flash deploy`, correct transcript.

```python
# whisper_worker.py  — deps + GPU declared in the decorator (NOT pyproject.toml)
from runpod_flash import Endpoint, GpuGroup

@Endpoint(
    name="whisper-flash",
    gpu=GpuGroup.AMPERE_16,                 # whisper base needs <2GB; broad supply
    workers=(0, 3), idle_timeout=60,        # scale-to-zero
    dependencies=["faster-whisper",
                  "nvidia-cublas-cu12", "nvidia-cudnn-cu12"],  # CTranslate2 GPU libs
)
async def transcribe(input_data: dict) -> dict:
    import base64, tempfile, urllib.request
    from faster_whisper import WhisperModel
    global _MODEL                            # load once per worker (see flash gotcha 11)
    try: _MODEL
    except NameError: _MODEL = WhisperModel("base", device="cuda", compute_type="float16")
    # download input_data["audio_url"] (or decode audio_base64) -> temp file -> transcribe
```

```bash
uv tool install runpod-flash          # or pip install runpod-flash (py 3.10-3.13)
export RUNPOD_API_KEY=...
flash init ~/whisper-flash            # scaffold (outside your git repos)
flash dev                             # iterate on a real remote GPU (hot-reload) — cheap, catches the payload shape
flash deploy                          # ship → returns an endpoint id
```

Call it (note the payload nests under the **parameter name** `input_data` — flash
gotcha 10; name the param `input` to get the plain contract):

```bash
curl -s https://api.runpod.ai/v2/<endpoint-id>/runsync \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":{"input_data":{"audio_url":"https://github.com/runpod-workers/sample-inputs/raw/main/audio/gettysburg.wav"}}}'
```

Verified: cold ~55–75s (image pull + model download), **warm <1s**; returns
`{text, language, ...}` with the correct Gettysburg transcript. Teardown:
`flash app delete whisper-flash` (or `runpodctl serverless delete <id>`).

### Hub vs flash — which to pick

- **Hub (Variant A):** ~2 min, zero code, but you take the worker's model/schema.
  Best for a **heavy, prebuilt, known** model where a maintained worker exists.
- **flash (Variant B):** ~15 min, you own the handler, model size, I/O, and get a
  **lighter/cheaper** image + `flash dev` iteration. Best for **custom/small**
  workloads or when no good Hub worker fits. For a big prebuilt model with a solid
  Hub worker, flash is just re-implementing it — stay on the Hub.

## Cost + cleanup

`--workers-min 0` ⇒ scale-to-zero: no GPU billing while idle (you pay only per
request-second, plus the free scale-to-zero). Delete when done:

```bash
runpodctl serverless delete <endpoint-id>
```

## Skill gaps found while doing this

- The stub said "deploy a Whisper worker from the Hub … if a suitable one exists" but
  gave no way to judge *which* Hub worker is suitable. Add the rule now captured
  above: **pick the actively-maintained worker on a high-availability GPU pool, and
  treat `ready` workers with `inProgress: 0` and queued jobs as a broken image —
  switch, don't wait.**
- `runpodctl serverless update` has **no `--gpu-id` flag**; to change an existing
  endpoint's GPU pool you must `PATCH https://rest.runpod.io/v1/endpoints/<id>` with
  `{"gpuTypeIds":[...]}`. Worth noting in the runpodctl skill.
- `runpodctl serverless create` accepts `--workers-min/--workers-max` but the Hub
  config controls the GPU pool; to override at create time pass `--gpu-id`. Scale-to-
  zero is `--workers-min 0` (the default when omitted).
- No first-class serverless **worker-log** access from runpodctl / REST v1 / GraphQL
  introspection (all dead ends here). Diagnosis relied on `/health` worker counts.
  A `runpodctl serverless logs <endpoint-id>` would have made the broken-worker call
  much faster.
