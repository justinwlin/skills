# Golden path 01 — Ollama server on a pod + access URL

**Goal:** from a plain request ("stand up an Ollama server on Runpod and give me
the URL"), an agent provisions a pod, installs and starts Ollama, pulls a model,
and returns a working HTTP API URL — with model data on persistent storage.

Grounded in the official tutorial: `docs/tutorials/pods/run-ollama.mdx`.

## Acceptance criteria

1. **Auth** resolved before any API call.
2. A GPU pod is created from an **official Runpod PyTorch template**, with
   **port `11434/http` exposed at creation** and env **`OLLAMA_HOST=0.0.0.0`**.
   SSH is enabled so the agent can run commands.
3. Ollama is installed and the server started; a model is pulled (e.g. `llama3`).
   Installs use package managers where possible (apt for system, **uv** for any
   Python tooling) to reduce breakage.
4. The agent **polls until the API answers** (`GET /api/tags` → 200), and if any
   step needs a human, it stops and says so.
5. Model storage is on a **network volume by default** (persists across restarts,
   avoids re-download), unless the user asks for ephemeral/pod disk.
6. The agent returns `https://<pod-id>-11434.proxy.runpod.net` and a sample call.

## Ideal agentic flow (runpodctl lane)

runpodctl is the right lane here: it exposes every flag this needs and gives a
non-interactive SSH channel. (MCP could create the pod, but see gaps below.)

```bash
# 0. Auth (once)
runpodctl doctor

# 1. Persistent model storage (default): a network volume in a DC with the GPU
runpodctl network-volume create --name ollama-models --size 50 --data-center-id <dc>
#   → note the volume id + its data center

# 2. Create the pod: pytorch template, GPU, port + env set AT creation, volume attached
runpodctl template search pytorch          # find the official PyTorch template id
runpodctl pod create \
  --name ollama \
  --template-id <runpod-pytorch-template-id> \
  --gpu-id "NVIDIA A40" \
  --ports "11434/http" \
  --env '{"OLLAMA_HOST":"0.0.0.0","OLLAMA_MODELS":"/workspace/ollama"}' \
  --network-volume-id <volume-id> \
  --volume-mount-path /workspace \
  --stop-after 2026-01-01T00:00:00Z      # always set a cleanup guard

# 3. Wait for the pod, then get the SSH connection
runpodctl pod get <pod-id>                 # poll until running
runpodctl ssh info <pod-id>                # non-interactive ssh command + key

# 4. Install + start Ollama over SSH (non-interactive, single command)
ssh <pod-ssh> 'apt update && apt install -y lshw zstd && \
  curl -fsSL https://ollama.com/install.sh | sh && \
  (ollama serve > /workspace/ollama.log 2>&1 &) && \
  sleep 3 && ollama pull llama3'

# 5. Poll readiness from OUTSIDE (proves the proxy + bind + port all work)
until curl -sf https://<pod-id>-11434.proxy.runpod.net/api/tags; do sleep 5; done

# 6. Return the URL
echo "Ollama: https://<pod-id>-11434.proxy.runpod.net  (POST /api/generate)"
```

## Runpod gotchas this path must respect

- **Ports are set at creation.** You cannot add an exposed HTTP port to a running
  pod without a reset — declare `11434/http` up front.
- **Bind to `0.0.0.0`.** Ollama defaults to `127.0.0.1`; without
  `OLLAMA_HOST=0.0.0.0` the proxy returns 502. (Env var, set at creation.)
- **Proxy is HTTPS + Cloudflare 100s cap.** Fine for the API; a very long single
  generation can hit the cap — prefer streaming or short prompts to verify.
- **Model storage.** Default models live in container disk and vanish on stop.
  Point `OLLAMA_MODELS` at the network volume (`/workspace/...`) so pulls persist.
- **Volume ↔ GPU data center.** A network volume is DC-locked; create the pod in
  the same DC as the volume or scheduling fails.
- **No auth on the endpoint.** The proxy URL is public and Ollama has no built-in
  auth — warn the user; don't expose sensitive models unprotected.

## Gap analysis — how far are we?

Capability is mostly present (runpodctl has every flag); the **skill guidance**
to run this agentically is what's thin.

| Requirement | Covered today | Gap |
| --- | --- | --- |
| Auth | ✅ router + runpodctl `doctor` / MCP OAuth | — |
| Pod: pytorch template + GPU | ✅ `pod create --template-id --gpu-id` | — |
| Expose port + env at creation | ✅ `--ports` / `--env`; now documented in `pod-workflows.md` + runpodctl | — |
| SSH enabled | ✅ `--ssh` defaults on; `ssh info` | — |
| **Agent runs commands on the pod** | ✅ `pod-workflows.md` — non-interactive `ssh <host> '…'` exec loop | — |
| Install hygiene / **uv** | ✅ `on-pod-setup.md` (apt for system, uv for Python, pin, background+log) | — |
| Poll readiness + escalate | ✅ `pod-workflows.md` steps 6 + 8 | — |
| Storage: default network volume | ✅ `storage.md` "Default: prefer a network volume" | — |
| Return access URL | ✅ `networking.md` has the proxy format | — |

### Skill changes (done)

Closed by generic capabilities, not Ollama-specific recipes:

1. **`runpod-usage/reference/pod-workflows.md`** — the reusable pod development
   loop (provision → ssh-exec → set up → run → poll readiness → escalate → deliver).
2. **`runpod-usage/reference/on-pod-setup.md`** — install hygiene (uv/apt, pin,
   non-interactive, cache on volume, background + log).
3. **`storage.md`** — "prefer a network volume by default" policy.
4. **Router + runpodctl** — service pods declare port + env at creation; both
   point at the pod development loop.

Remaining to reach **covered**: a live end-to-end run on a fundable account.
