# Golden path 02 — ComfyUI server on a pod + access URL

**Goal:** from "run ComfyUI on Runpod and give me the URL", an agent provisions a
GPU pod, installs and starts ComfyUI, and returns a URL where the web UI loads —
with a checkpoint + the default text-to-image workflow already usable.

Same shape as `01-ollama-pod.md`; follow `runpod-usage/reference/pod-workflows.md`.

## Acceptance criteria

1. **Auth** resolved (`export RUNPOD_API_KEY=...`).
2. GPU pod from an **official PyTorch template**, GPU with ≥16 GB VRAM (RTX 4090
   is ideal), **port `8188/http` exposed at creation**, SSH enabled, on a network
   volume, with a `--terminate-after` guard.
3. ComfyUI installed; **deps installed into the template's existing torch** (not a
   fresh venv — see gap A); server started **fully detached**, bound to `0.0.0.0`.
4. Agent **polls the proxy URL until the UI answers** (expect ~30–60s of 502s
   during boot); escalates on any manual step.
5. **Secondary:** an ungated checkpoint is pre-loaded so the default graph works;
   ideally a generation is confirmed via the API.
6. Returns `https://<pod-id>-8188.proxy.runpod.net`.

## Ideal agentic flow (runpodctl lane)

```bash
export RUNPOD_API_KEY=your_key

runpodctl datacenter list                       # pick a DC with the GPU
runpodctl network-volume create --name comfy --size 50 --data-center-id <dc>
runpodctl template search pytorch               # official PyTorch template id

runpodctl pod create --name comfyui \
  --template-id <runpod-pytorch-template-id> \
  --gpu-id "NVIDIA GeForce RTX 4090" --data-center-ids <dc> \
  --ports "8188/http,22/tcp" \
  --network-volume-id <volume-id> --volume-mount-path /workspace \
  --ssh --terminate-after <iso8601 a few hours out>

runpodctl pod get <pod-id>                       # poll until running
runpodctl ssh info <pod-id>                       # ssh connection

# install (into the template's torch — see gap A) + fetch the checkpoint
ssh <pod-ssh> 'set -e; cd /workspace && \
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI && \
  cd ComfyUI && pip install --break-system-packages -r requirements.txt && \
  curl -L -o models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors \
    https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive/resolve/main/v1-5-pruned-emaonly-fp16.safetensors'

# start FULLY DETACHED (survives ssh disconnect), return immediately
ssh <pod-ssh> 'setsid bash -c "cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188" \
  > /workspace/comfyui.log 2>&1 < /dev/null &'

# poll readiness from OUTSIDE (expect ~60s of 502s first)
until curl -sf https://<pod-id>-8188.proxy.runpod.net/system_stats; do sleep 5; done
echo "ComfyUI: https://<pod-id>-8188.proxy.runpod.net"
```

The checkpoint filename `v1-5-pruned-emaonly-fp16.safetensors` is exactly what
ComfyUI's default graph references, so the UI is usable on first open: tweak the
prompt → **Queue Prompt**. To verify programmatically: POST the default graph to
`/prompt`, poll `/history/<id>`, fetch `/view?filename=<out>&type=output`.

## Prebuilt image / official template (faster) — live-verified 2026-07-07

Instead of installing ComfyUI onto a PyTorch template, deploy Runpod's **official
prebuilt ComfyUI image** — ComfyUI + deps + custom nodes are baked in and it
**auto-starts** on boot. No SSH, no `pip install`, no `python main.py` needed.

```bash
runpodctl template search comfyui        # discovery
# Official (isRunpod:true): "ComfyUI - CUDA 12.8"  id cw3nka7d08  image runpod/comfyui:cuda12.8
#   (CUDA 13 / Blackwell / RTX 5090 → use "ComfyUI - CUDA 13" id 2lv7ev3wfp)

runpodctl pod create --name comfyui-prebuilt \
  --template-id cw3nka7d08 \
  --gpu-id "NVIDIA GeForce RTX 4090" --data-center-ids <dc-with-4090-and-volume> \
  --ports "8188/http,8080/http,8888/http,22/tcp" \
  --network-volume-id <volume-id> --volume-mount-path /workspace \
  --ssh --terminate-after <iso8601 a few hours out>

# ComfyUI auto-starts — just poll the proxy (NO install/run step)
until curl -sf https://<pod-id>-8188.proxy.runpod.net/system_stats; do sleep 10; done
```

Facts (verified on pod `7ydkt5vs4fst25`, RTX 4090, $0.69/hr):

- **Template:** `ComfyUI - CUDA 12.8`, id `cw3nka7d08`, image `runpod/comfyui:cuda12.8`,
  `isRunpod: true` (Runpod-maintained; source: `github.com/runpod-workers/comfyui-base`).
- **Ports baked into the template:** `8188` ComfyUI, `8080` FileBrowser
  (admin / adminadmin12), `8888` JupyterLab (`JUPYTER_PASSWORD`), `22` SSH.
- **Auto-starts:** yes — `main.py --listen 0.0.0.0 --port 8188 --enable-cors-header`
  already running (bind + CORS handled for you). Ships ComfyUI 0.26.2, torch 2.10.0+cu128.
- **Boot time:** ~4 min of proxy `502`s (it copies ComfyUI to `/workspace` on first
  boot — onto a network volume this is the slow part; readiness log line is
  `[ComfyUI-Manager] All startup tasks have been completed.`). Install path:
  `/workspace/runpod-slim/ComfyUI`; args file `/workspace/runpod-slim/comfyui_args.txt`.
- **No model ships** — `/models/checkpoints` is empty on boot (a gap vs "usable on
  first open"). Two ways to add one:
  - **From the UI (easiest for a human):** the prebuilt image bundles
    **ComfyUI-Manager**, so when a loaded workflow references a missing model the UI
    shows a **blue "download" / missing-models button** that fetches the model
    **straight into the correct Runpod folder** — no need to find the URL or the
    right `models/` subdirectory yourself.
  - **Programmatically (for an agent):** drop the file into
    `/workspace/runpod-slim/ComfyUI/models/checkpoints/` over SSH (same filename the
    default graph references); ComfyUI rescans on the next `/object_info` request, no
    restart needed. Agents use this path since they don't click UI buttons.
- **Effort vs from-scratch:** fewer steps — creation + poll only; skip the entire
  `git clone` + `pip install --break-system-packages` + `setsid … python main.py`
  block and the PEP 668 / detach gotchas. Trade-off: larger image (150 GB container
  disk) and the ~4-min first-boot copy. Adding a checkpoint is the only SSH step.

## Runpod gotchas this path must respect

- **PEP 668 / template torch (gap A).** The current PyTorch template is
  Ubuntu 24.04 / py3.12 (externally-managed) with torch in the **system** Python.
  `pip install` errors without `--break-system-packages`, and a bare `uv venv`
  won't inherit torch. Install into the existing interpreter.
- **Detach the server (gap B).** A plain `&` dies on SSH disconnect (SIGHUP).
  Use `setsid … < /dev/null &` and return immediately; poll in a separate call.
- **Proxy warm-up 502s.** The proxy 502s for ~30–60s while ComfyUI imports/inits
  CUDA — keep polling.
- **Bind `0.0.0.0`** via `--listen 0.0.0.0` (localhost → proxy 502).
- **Ports at creation**; **volume ↔ GPU same DC**; **URL is public + unauth**.

## Status: COVERED — live-verified 2026-07-07

Ran end to end: pod (RTX 4090, PyTorch template, port 8188, network volume) →
`pip install --break-system-packages -r requirements.txt` → SD1.5 checkpoint
(2.1 GB, ungated `Comfy-Org/stable-diffusion-v1-5-archive`) → ComfyUI started
detached, bound `0.0.0.0` → external `/system_stats` 200 → default workflow POSTed
to `/prompt` → **512×512 PNG produced**. New findings (PEP 668, detached-process
survival, proxy warm-up) folded into `pod-workflows.md` / `on-pod-setup.md`.
