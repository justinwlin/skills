# Golden path 04 — LoRA fine-tune (training run) on a pod

**Goal:** from "fine-tune a small model on Runpod", an agent provisions a GPU pod
with a **network volume for datasets + checkpoints**, sets up training deps,
launches a **detached, logged** LoRA/QLoRA run, monitors it to completion, and
leaves the trained adapter on the volume — then tears the pod down.

This is a **batch job on a pod**, not a server. It follows the pod development
loop (`../runpod-usage/reference/pod-workflows.md`) but the shape differs at both
ends: there is **no port / proxy URL** to expose, and **success is "training
finished + checkpoint on the volume"**, verified by tailing the log — not by
polling an HTTP endpoint. See `../runpod-usage/reference/development-loop.md` for
the shared spine.

Grounded in: `docs/instant-clusters/axolotl.mdx` (single-node adaptation of the
`torchrun … axolotl.cli.train` flow), `on-pod-setup.md`, `storage.md`,
`gpu-selection.md`.

## Acceptance criteria

1. **Auth** resolved (`export RUNPOD_API_KEY=...`) before any API call.
2. GPU pod from an **official PyTorch template**, GPU sized for **training** (see
   gotcha — training needs far more VRAM than inference), SSH enabled, a
   **network volume at `/workspace`**, and a `--terminate-after` cost guard.
   No `--ports` are needed — there is no service to expose.
3. Dataset + base model are fetched to the **volume** (`hf download` into
   `/workspace`, `HF_HOME=/workspace/hf-cache`) so a restart doesn't re-download.
4. Training deps installed into the **template's existing torch** (PEP 668 /
   `--break-system-packages` — see gotcha), not a fresh venv.
5. Training launched **detached** (`setsid … </dev/null &`), **logging to the
   volume**, so it survives SSH disconnect. The agent returns immediately and
   monitors in separate calls.
6. Agent **monitors to completion** by tailing the log (loss going down, then the
   final "training completed / saving model" line) and/or `nvidia-smi` — not by
   polling a URL.
7. On completion, the **checkpoint/adapter persists on the volume**
   (`/workspace/outputs/...`). Agent reports the path; escalates on any manual
   step (gated model/dataset license, OOM needing a bigger GPU).

## Ideal agentic flow (runpodctl lane)

```bash
export RUNPOD_API_KEY=your_key

# 1. Plan storage first: a network volume for datasets + checkpoints (persists)
runpodctl datacenter list                          # pick a DC that has the GPU
runpodctl network-volume create --name ft-data --size 100 --data-center-id <dc>

# 2. Provision — training GPU, PyTorch template, volume, SSH, terminate guard.
#    NO --ports: a training run exposes nothing.
runpodctl template search pytorch                  # official PyTorch template id
runpodctl pod create --name lora-ft \
  --template-id <runpod-pytorch-template-id> \
  --gpu-id "NVIDIA GeForce RTX 4090" --data-center-ids <dc> \
  --network-volume-id <volume-id> --volume-mount-path /workspace \
  --ssh --terminate-after <iso8601 well past the expected run time>

runpodctl pod get <pod-id>                          # poll until running
runpodctl ssh info <pod-id>                          # ssh command + key

# 3. Set up deps INTO the template torch (PEP 668) + fetch data/model to the volume.
#    Do the long install/download in the background, logged to the volume.
ssh <pod-ssh> 'set -e; export HF_HOME=/workspace/hf-cache; \
  cd /workspace && git clone --depth 1 https://github.com/axolotl-ai-cloud/axolotl && \
  cd axolotl && \
  pip install --break-system-packages -U packaging setuptools wheel ninja && \
  pip install --break-system-packages --no-build-isolation -e ".[flash-attn,deepspeed]" \
    > /workspace/setup.log 2>&1'
ssh <pod-ssh> 'tail -n 20 /workspace/setup.log'      # confirm setup finished (separate call)

# 4. Launch training DETACHED, logged to the volume. Point outputs at /workspace.
#    (axolotl's llama-3 LoRA example fine-tunes a small Llama on a bundled dataset;
#     swap in your own config/dataset. HF_TOKEN needed only for a gated base model.)
ssh <pod-ssh> 'export HF_HOME=/workspace/hf-cache HF_TOKEN=<if-gated>; \
  cd /workspace/axolotl/examples/llama-3 && \
  setsid bash -c "python -m axolotl.cli.train lora-1b.yml \
    --output_dir /workspace/outputs/lora-out" \
    > /workspace/train.log 2>&1 < /dev/null &'

# 5. Monitor to completion (separate calls — this is the "verify" step for a batch job)
ssh <pod-ssh> 'tail -n 30 /workspace/train.log'      # loss should trend down
ssh <pod-ssh> 'nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv'
# done when the log shows the final line, e.g.
#   "Training completed! Saving pre-trained model to ./outputs/lora-out"

# 6. Confirm the artifact persisted on the volume, then report + tear down
ssh <pod-ssh> 'ls -la /workspace/outputs/lora-out'   # adapter_model.safetensors etc.
runpodctl pod remove <pod-id>                        # volume (with the adapter) survives
```

## Why the loop differs from a server (01/02)

- **No proxy URL, no port, no `0.0.0.0` bind.** Nothing is exposed; skip the
  "expose port at creation" and "poll the proxy" steps entirely.
- **Verify = the log, not a URL.** "Pod Running" and even "GPU busy" don't mean
  the run is healthy — read the log for a falling loss and the final save line.
  A run that finishes in seconds with no checkpoint is a failure, not a success.
- **Detach is still mandatory** (a long run must survive SSH SIGHUP), but the
  payoff is a finished artifact, not a live server. `setsid … </dev/null &` +
  monitor in separate calls; don't `sleep` in the launch invocation.
- **Checkpoints are the deliverable.** They must land under `/workspace` (the
  network volume) so they outlive the terminated pod. Anything written to
  container disk is gone on teardown (`storage.md`).

## Runpod gotchas this path must respect

- **Size VRAM for training, not inference.** Weights + gradients + optimizer
  state + activations ≈ ~4x the inference figure for full fine-tuning; LoRA/QLoRA
  cut this a lot but still budget headroom (`gpu-selection.md`). If the run OOMs,
  escalate to a bigger tier or enable QLoRA — don't silently retry.
- **PEP 668 / template torch.** Official PyTorch templates are Ubuntu 24.04 /
  py3.12 with torch in the **system** Python. `pip install` needs
  `--break-system-packages`; a bare `uv venv` won't inherit torch. Install into
  the existing interpreter (`on-pod-setup.md`).
- **Detach the run.** A plain `&` dies on SSH disconnect (SIGHUP). Use
  `setsid … < /dev/null &` and monitor in separate SSH calls.
- **Persist everything on the volume.** Base model + dataset (`HF_HOME` →
  `/workspace/hf-cache`) and `--output_dir /workspace/...`. Container disk is
  wiped on stop/terminate.
- **Volume ↔ GPU same DC.** A network volume is DC-locked; create the pod in the
  volume's DC or scheduling fails (`storage.md`).
- **Gated base model / dataset.** `hf download` of a gated repo needs `HF_TOKEN`
  and an accepted license — a manual step. If it 401/403s, **stop and ask** for
  the token / license acceptance.
- **`--terminate-after` must exceed the run.** It *deletes* the pod at that time;
  set it well past the expected training duration or you'll lose an in-flight run
  (the checkpoint on the volume survives, but a mid-run kill wastes the compute).

## Status: SPEC (not yet live-verified)

Unlike golden paths 01–03 (live-verified), this path has **not** been run end to
end on a real account. The flow, resource shape, and gotchas are grounded in the
skills and `docs/instant-clusters/axolotl.mdx`, but exact axolotl example
config/flag names (`lora-1b.yml`, `--output_dir`), the training GPU sizing, and
the completion log string should be confirmed on a real run before this is marked
covered.
