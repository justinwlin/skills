# Golden path 08 — fine-tune → serve (LoRA on a pod → serverless)

**Goal:** the smallest end-to-end **train-then-serve** loop: LoRA-fine-tune a tiny LLM
on a **pod** with axolotl, write the adapter to a **network volume**, then load base +
adapter from that same volume on a **serverless** endpoint and generate. Designed as a
fast/cheap validation that **scales to larger models by changing three things** (model id,
GPU, dataset) — nothing structural changes.
**Status:** SPEC (not yet live-run). Composes two verified pieces: the network-volume
handoff (golden path [07](07-network-volume-handoff.md), live-verified) and the axolotl
training flow (golden path [04](04-finetune-pod.md)). Exact axolotl flags/paths are grounded
in the docs; confirm on a real run.
**Lane(s):** runpodctl (pod + volume) + flash (serverless) + Runpod MCP (`stream-worker-logs`, for diagnosis)

## The loop in one picture
```
[pod: axolotl train]  --writes-->  /workspace/outputs/lora-out   (network volume)
                                          | same volume, different mount path
[serverless worker]   --reads-->   /runpod-volume/outputs/lora-out  --> base+adapter --> generate
```
This is golden path 07's handoff with a LoRA adapter as the payload instead of a text file.
Read [07](07-network-volume-handoff.md) first — the `/workspace` (pod) vs `/runpod-volume`
(serverless) mount-path rule and the flash handler contract are the two things that bite.

## Why start tiny
Pick the **smallest model that proves the pipeline**, get the whole loop green, then scale
only the model id + GPU. Validation defaults:

| Knob | Validation value | Scale up by |
| --- | --- | --- |
| Base model | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (1.1B, ungated) | swap to Llama-3.1-8B, Qwen2.5-14B, … |
| GPU | one RTX 4090 (`ADA_24`) | bigger VRAM tier (see `../skills/runpod-usage/reference/gpu-selection.md`); QLoRA for memory |
| Dataset / steps | axolotl's bundled alpaca example, a few dozen steps | your dataset + full epochs |
| Serving | transformers + PEFT (simple) | vLLM with LoRA for throughput |

A 1.1B LoRA on a 4090 trains in **minutes** — fast enough to iterate the loop itself before
spending on a real run.

## Prerequisites
- `RUNPOD_API_KEY` resolvable; `runpodctl` + `flash` installed.
- An SSH key registered **before** creating the pod (`runpodctl ssh list-keys`; see
  `../skills/runpod-usage/reference/getting-started.md`).
- `HF_TOKEN` only if you scale to a **gated** base model (TinyLlama is ungated).

## 1. Storage — one volume, reused across both phases
```bash
runpodctl network-volume create --name ft-loop --size 30 --data-center-id <dc>
# → <vol-id>, pinned to <dc>. The pod AND the endpoint must run in this DC.
```

## 2. Train on a pod (axolotl → adapter on the volume)
```bash
runpodctl pod create --name ft-train \
  --template-id runpod-torch-v280 --gpu-id "NVIDIA GeForce RTX 4090" \
  --data-center-ids <dc> \
  --network-volume-id <vol-id> --volume-mount-path /workspace \
  --ssh --terminate-after <iso8601 a few hours out>          # no --ports: training serves nothing
```
Then over SSH (see 07 for the poll-until-ready + non-interactive `ssh` pattern):
```bash
# install into the template's torch (PEP 668) and keep the HF cache on the volume
pip install --break-system-packages "axolotl[flash-attn]" || pip install --break-system-packages axolotl
export HF_HOME=/workspace/hf-cache

# grab axolotl's tiny LoRA example and point outputs at the VOLUME
axolotl fetch examples
axolotl train examples/tiny-llama/lora.yml \
  --output_dir /workspace/outputs/lora-out            # adapter lands on the volume
```
Success = the log ends with a "training complete / saving model" line and the adapter files
exist: `ls /workspace/outputs/lora-out` shows `adapter_config.json` + `adapter_model.safetensors`.
Then free the GPU — the volume keeps the adapter:
```bash
runpodctl pod remove <pod-id>
```
> Training is a **batch job**, not a server: monitor by tailing the log, not by polling a URL
> (golden path [04](04-finetune-pod.md)). Launch it detached (`setsid … </dev/null &`) for a
> long run so it survives SSH disconnect.

## 3. Serve on serverless (load base + adapter from `/runpod-volume`)
A flash endpoint attaches the **same volume** and loads the adapter once per worker.
Mind the two things from 07: mount path is `/runpod-volume`, and the handler is called as
`handler(**job_input)` (use `**kwargs`; empty input is rejected).

```python
# main.py
import os
from runpod_flash import Endpoint, GpuGroup, DataCenter, NetworkVolume

vol = NetworkVolume(id="<vol-id>", datacenter=DataCenter.<DC>)   # the SAME volume
ADAPTER = "/runpod-volume/outputs/lora-out"
BASE = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

@Endpoint(
    name="ft-serve",
    gpu=GpuGroup.ADA_24,                 # match to the base model's VRAM
    workers=(0, 1),                      # scale to zero
    datacenter=DataCenter.<DC>,
    volume=vol,
    env={"HF_HUB_CACHE": "/runpod-volume/hf-cache"},   # reuse the cache from training
    dependencies=["torch", "transformers", "peft", "accelerate"],
)
class Serve:
    def __init__(self):                  # runs ONCE per worker (flash gotcha: load once)
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        self.tok = AutoTokenizer.from_pretrained(BASE)
        base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float16).to("cuda")
        self.model = PeftModel.from_pretrained(base, ADAPTER)   # base + LoRA from the volume

    async def generate(self, **kwargs) -> dict:      # **kwargs: flash spreads input as kwargs
        prompt = kwargs.get("prompt", "Hello")
        ids = self.tok(prompt, return_tensors="pt").to("cuda")
        out = self.model.generate(**ids, max_new_tokens=kwargs.get("max_new_tokens", 64))
        return {"text": self.tok.decode(out[0], skip_special_tokens=True)}
```
```bash
RUNPOD_API_KEY=... flash deploy
runpodctl serverless list        # confirm the endpoint's networkVolumeId == <vol-id>
```

## 4. Verify with a real request
Send a **non-empty** input (empty `{}` is rejected — see 07):
```bash
curl -s https://api.runpod.ai/v2/<endpoint-id>/run -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"Give me one tip about GPUs."}}'    # then poll /status/<job-id>
```
Green when the first (cold) call returns generated `text`. The pipeline is proven; now scale.

## Scaling to a larger model (what changes — and what doesn't)
**Changes:** `BASE` (model id in the axolotl config + the serve handler), the `--gpu-id` /
`GpuGroup` to a bigger-VRAM tier, and dataset/steps. Add `HF_TOKEN` for gated models. Use
**QLoRA** (axolotl `load_in_4bit: true`) when the base won't fit for full LoRA.
**Doesn't change:** the loop — one volume, pod writes the adapter to `/workspace/outputs`,
serverless reads it from `/runpod-volume/outputs`, same DC, `**kwargs` handler, non-empty
input. For high-throughput serving, swap the transformers handler for **vLLM with LoRA**
(load the base once, hot-swap adapters) — same volume handoff.

## Cost & cleanup
```bash
runpodctl serverless delete <endpoint-id>     # (undeploy+redeploy for fresh workers if a code change is stuck — see 07)
runpodctl network-volume delete <vol-id>      # pod already removed; deletes the adapter + cache
```
Pod cost guard: `--terminate-after` (deletes the pod), not `--stop-after`. Endpoint is
scale-to-zero (`workers=(0,1)`), ~$0 idle. Keep the volume only while iterating.

## Gotchas this path inherits
- **Mount-path swap:** `/workspace` on the pod == `/runpod-volume` on serverless — same volume,
  different path ([07](07-network-volume-handoff.md), `storage.md`).
- **flash handler contract:** `handler(**job_input)` — use `**kwargs`; invoke with non-empty
  `input` (flash SKILL gotcha "Request body shape").
- **Load the model once** in the class `__init__`, not per request (flash SKILL gotcha).
- **PEP 668** on the training pod: `pip install --break-system-packages …` (`on-pod-setup.md`).
- **Diagnosis:** if the endpoint job times out, pull worker logs with the MCP
  `stream-worker-logs` before assuming a broken worker — it's usually a payload/handler issue.
- **Same DC** for volume + pod + endpoint (the volume is DC-pinned).
