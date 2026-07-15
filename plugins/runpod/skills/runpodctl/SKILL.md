---
name: runpodctl
description: >-
  Runpod CLI for managing GPU/CPU workloads from the terminal — pods, serverless
  endpoints, templates, network volumes, Hub deploys, models, SSH, and file
  transfer (send/receive). Use for terminal/CI/scripting, Hub browse/deploy, SSH
  setup, `doctor`, or when the Runpod MCP tools are not connected. For structured
  tool calls in an MCP-enabled session, prefer runpod-mcp.
allowed-tools: Bash(runpodctl:*)
compatibility: Linux, macOS
metadata:
  author: runpod
  version: "2.3"
license: Apache-2.0
---

# Runpodctl

Manage GPU pods, serverless endpoints, templates, volumes, and models.

## Install

`curl -sSL https://cli.runpod.net | bash` (any platform) or `brew install runpod/runpodctl/runpodctl`. Manual binaries, Windows/Linux steps, and the version caveat (`--model-reference` + multi-volume need **v2.4.0+**): **[reference/install.md](reference/install.md)**.

> **Always get on the latest runpodctl first — don't use whatever's already installed.**
> Run `runpodctl version`, then `runpodctl update` (or reinstall from the
> [latest release](https://github.com/runpod/runpodctl/releases)) **before doing any work**.
> Older builds silently lack newer flags/behaviors (e.g. `--model-reference` doesn't exist
> before v2.4.0) and produce confusing downstream errors — and the Homebrew tap can lag
> well behind. Pin to one recent version for the whole task; **do not switch between an old
> and a new binary mid-task** (that mid-task version flip-flop is a known failure). Verify
> once: `runpodctl version` shows the current build before you continue.

## Quick start

```bash
runpodctl update                    # FIRST: get on the latest build — old versions cause confusing errors
runpodctl version                   # confirm the current version before doing any work
export RUNPOD_API_KEY=your_key      # Non-interactive auth (agents) — runpodctl reads this
runpodctl doctor                    # Interactive first-time setup (API key + SSH) — for humans
runpodctl --help                    # See current top-level commands
runpodctl pod create --help         # Inspect exact current flags before creating
runpodctl gpu list                  # See available GPU types
runpodctl datacenter list           # GPU availability per data center (use to co-locate GPU + volume)
runpodctl hub search vllm           # Find a hub repo
runpodctl serverless create --hub-id <id> --name "my-vllm"  # Deploy from hub
runpodctl template search pytorch   # Find a template
runpodctl pod create --template-id runpod-torch-v21 --gpu-id "NVIDIA GeForce RTX 4090"  # Create from template
runpodctl pod list                  # List your pods
```

> Auth: an agent should `export RUNPOD_API_KEY=...` (non-interactive). `runpodctl
> doctor` is interactive (prompts) and also sets up SSH keys — good for a human's
> first run, not for scripted use.

API key: https://console.runpod.io/user/settings

## Live Help Is Authoritative

Live `runpodctl --help` output is authoritative for exact flags, aliases, and command syntax. Use this skill for workflows, decision rules, safety notes, and common examples.

```bash
runpodctl --help
runpodctl <resource> --help
runpodctl <resource> <action> --help
```

Before using unfamiliar commands, inspect live help first. Do not rely on this skill as an exhaustive flag reference.

## Decision Rules

- Use Hub when the user wants a known deployable app or worker such as vLLM, ComfyUI, Whisper, or a Runpod-maintained repo. Picking a worker: prefer an actively-maintained one on a **broad, high-availability GPU pool** (don't pin a scarce large tier a small model doesn't need). If deployed workers go `ready` but jobs sit `IN_QUEUE` with `inProgress: 0`, that image is broken/mis-dispatching — switch workers, don't wait it out. Note: there's no first-class serverless worker-log command, so diagnose via `/health` worker counts.
- Serverless endpoints scale to zero with `--workers-min 0` (the default) — no GPU billing while idle, only per request-second. This is the right cost posture for a request/response API. `serverless update` has no `--gpu-id`; to change an existing endpoint's GPU pool, `PATCH https://rest.runpod.io/v1/endpoints/<id>` with `{"gpuTypeIds":[...]}`.
- Use templates when the user already has a template ID, wants reusable image/config defaults, or needs lower-level control than Hub.
- Use direct pod creation with `--image` when the user has a specific Docker image and does not need a saved template.
- Use serverless for request/response inference APIs and scalable workers; use pods for interactive work, notebooks, training, debugging, or long-lived sessions.
- Use CPU pods for preprocessing, file movement, lightweight scripts, and non-CUDA work. Use GPU pods when CUDA, model inference, training, or GPU memory is required.
- Do not pass GPU flags when creating CPU pods. Check `runpodctl pod create --help` for the current valid flag set.
- Standing up a **service on a pod** (Ollama, ComfyUI, a dev server)? Declare its `--ports` and `--env` **at creation** (they can't be added to a running pod without a reset), then follow the pod development loop in the `runpod-usage` skill (`reference/pod-workflows.md`) — SSH-exec the install, bind to `0.0.0.0`, and poll the proxy URL until it answers.
- For SSH, prefer `runpodctl pod get <pod-id>` or `runpodctl ssh info <pod-id>` to retrieve connection details. Do not use deprecated interactive SSH commands.
- Network volumes are location-sensitive. Check datacenter availability before attaching volumes, and use `send` / `receive` or S3-compatible storage for migrations.
- Clean up paid resources after tests: delete serverless endpoints, pods, and temporary volumes created for validation. As a cost guard on creation use `--terminate-after` (deletes the pod); `--stop-after` only *stops* it, so disk/volume keep billing. To delete an attached network volume, remove the pod first.

## Commands

### Pods

```bash
runpodctl pod list                                    # List running pods (default, like docker ps)
runpodctl pod list --all                              # List all pods including exited
runpodctl pod list --status exited                    # Filter by status (RUNNING, EXITED, etc.)
runpodctl pod list --since 24h                        # Pods created within last 24 hours
runpodctl pod list --created-after 2025-01-15         # Pods created after date
runpodctl pod get <pod-id>                            # Get pod details (includes SSH info)
runpodctl pod create --template-id runpod-torch-v21 --gpu-id "NVIDIA GeForce RTX 4090"  # Create from template
runpodctl pod create --image "runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404" --gpu-id "NVIDIA GeForce RTX 4090"  # Create with image
runpodctl pod create --compute-type cpu --image ubuntu:22.04  # Create CPU pod
runpodctl pod start <pod-id>                          # Start stopped pod
runpodctl pod stop <pod-id>                           # Stop running pod
runpodctl pod restart <pod-id>                        # Restart pod
runpodctl pod reset <pod-id>                          # Reset pod
runpodctl pod update <pod-id> --name "new"            # Update pod
runpodctl pod delete <pod-id>                         # Delete pod (aliases: rm, remove)
```

For exact pod flags, run `runpodctl pod <action> --help`.

### Hub

Browse and search the Runpod Hub — a curated marketplace of deployable repos.

```bash
runpodctl hub list                                    # Top 10 by stars
runpodctl hub list --type SERVERLESS                  # Only serverless repos
runpodctl hub list --type POD                         # Only pod repos
runpodctl hub list --category ai --limit 20           # Filter by category
runpodctl hub list --order-by deploys                 # Order by deploys
runpodctl hub list --owner runpod-workers             # Filter by repo owner
runpodctl hub search vllm                             # Search for "vllm"
runpodctl hub search whisper --type SERVERLESS        # Search serverless repos
runpodctl hub get <listing-id>                        # Get by listing id
runpodctl hub get runpod-workers/worker-vllm          # Get by owner/name
```

For exact Hub flags, run `runpodctl hub <action> --help`.

### Serverless (alias: sls)

```bash
runpodctl serverless list                             # List all endpoints
runpodctl serverless get <endpoint-id>                # Get endpoint details
runpodctl serverless create --name "x" --template-id "tpl_abc"  # Create from template
runpodctl serverless create --name "x" --hub-id <listing-id>    # Create from hub repo
runpodctl serverless create --hub-id <id> --env MODEL_NAME=my-model  # Override hub env defaults
runpodctl serverless create --template-id <id> --gpu-id "NVIDIA GeForce RTX 4090" --model-reference https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct:main  # Attach & cache a HF model (template or hub, GPU only)
runpodctl serverless create --hub-id <id> --gpu-id "NVIDIA GeForce RTX 4090" --model-reference https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct:main  # Attach a model on a hub deploy
runpodctl serverless update <endpoint-id> --workers-max 5       # Update endpoint
runpodctl serverless delete <endpoint-id>             # Delete endpoint
```

**Create from hub:** `--hub-id` resolves the hub listing, extracts the build image and config (GPU IDs, container disk, env vars), creates an inline template, and deploys. Accepts both SERVERLESS and POD listing types. GPU IDs and env var defaults from the hub config are included automatically; override with `--gpu-id` and `--env`.

**CPU serverless endpoints:** always use `runpodctl serverless create --compute-type CPU` (optionally `--instance-id`, e.g. `cpu3g-4-16`) — or the MCP server. **Do not** create a CPU endpoint via the **public control REST** `POST https://rest.runpod.io/v1/endpoints` with `"computeType":"CPU"` — that silently provisions a **GPU** endpoint instead (verified 2026-07-14: the created endpoint comes back with `gpuCount:1` and `cpuFlavorIds:null`; `runpodctl --compute-type CPU` correctly returns `computeType:"CPU"` with `instanceIds:["cpu3g-4-16"]`). The MCP server drives Runpod's internal **REST v2** and handles this correctly; the public REST is v1-only (`rest.runpod.io/v2` just redirects to docs). Note the separate **runtime/invoke** API `https://api.runpod.ai/v2/<endpoint-id>/…` (health/run/runsync/openai) is a different v2 and works fine — the v1-vs-v2 caveat here is only about the **control/management** REST.

**Model cache (`--model-reference`):** Attach a Hugging Face model to the endpoint by full URL with a ref, e.g. `https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct:main`. Runpod caches it host-side in the standard HF cache dir (`/runpod-volume/huggingface-cache/hub/`), so the worker loads it directly — no bake, no volume. Repeatable; works with `--template-id`/`--hub-id`, GPU only, **runpodctl v2.4.0+**. Full mechanics + how it compares to baking / network volume / the Model Repository: **[reference/model-caching.md](reference/model-caching.md)**. Worked end-to-end: golden path [20 — model-caching endpoint](../runpod/golden-paths/20-model-caching-endpoint.md).

**Multi-region / high-availability (`--network-volume-ids`):** attach **multiple** network
volumes (one per data center) so workers spread across DCs instead of being pinned to one —
`runpodctl serverless create --template-id <t> --network-volume-ids <v1>,<v2> --data-center-ids <dc1>,<dc2> …`.
**Requires runpodctl ≥ v2.4.0** (older versions don't support multi-volume attach). Check
`runpodctl version`; the Homebrew tap can lag, so prefer the
[GitHub releases](https://github.com/runpod/runpodctl/releases) binary. Data does **not**
sync between volumes automatically — see golden path
[10 — multi-region HA serverless](../runpod/golden-paths/10-multi-region-ha-serverless.md).

For exact serverless flags, run `runpodctl serverless <action> --help`.

### Templates (alias: tpl)

```bash
runpodctl template list                               # Official + community (first 10)
runpodctl template list --type official               # All official templates
runpodctl template list --type community              # Community templates (first 10)
runpodctl template list --type user                   # Your own templates
runpodctl template list --all                         # Everything including user
runpodctl template list --limit 50                    # Show 50 templates
runpodctl template search pytorch                     # Search for "pytorch" templates
runpodctl template search comfyui --limit 5           # Search, limit to 5 results
runpodctl template search vllm --type official        # Search only official
runpodctl template get <template-id>                  # Get template details (includes README, env, ports)
runpodctl template create --name "x" --image "img"    # Create template
runpodctl template create --name "x" --image "img" --serverless  # Create serverless template
runpodctl template update <template-id> --name "new"  # Update template
runpodctl template delete <template-id>               # Delete template
```

For exact template flags, run `runpodctl template <action> --help`.

### Network Volumes (alias: nv)

```bash
runpodctl network-volume list                         # List all volumes
runpodctl network-volume get <volume-id>              # Get volume details
runpodctl network-volume create --name "x" --size 100 --data-center-id "US-GA-1"  # Create volume
runpodctl network-volume update <volume-id> --name "new"  # Update volume
runpodctl network-volume delete <volume-id>           # Delete volume
```

For exact network volume flags, run `runpodctl network-volume <action> --help`.

### Models (Model Repository)

`runpodctl model` manages the **Runpod Model Repository** — managed, versioned storage
for your **own** model artifacts (upload once, distributed to workers; not pinned to a
data center like a network volume). What it is, why/how, migrating off a baked-in model,
and Model-Repo-vs-volume: **[reference/model-caching.md](reference/model-caching.md)**.

```bash
runpodctl model list                                  # List your models
runpodctl model list --all                            # List all models (not just yours)
runpodctl model list --name "llama"                   # Filter by name
runpodctl model list --provider "meta"                # Filter by provider
runpodctl model add --name "my-model" --model-path ./model   # Upload a local model dir (multipart)
runpodctl model remove --name "my-model" --owner <owner>     # Remove a model
```

For exact model flags, run `runpodctl model <action> --help` (authoritative — `model add`
supports upload sessions, versioning, metadata, and private-source credentials).

### Registry (alias: reg)

```bash
runpodctl registry list                               # List registry auths
runpodctl registry get <registry-id>                  # Get registry auth
runpodctl registry create --name "x" --username "u" --password "p"  # Create registry auth
runpodctl registry delete <registry-id>               # Delete registry auth
```

For exact registry flags, run `runpodctl registry <action> --help`.

### Info

```bash
runpodctl user                                        # Account info and balance (alias: me)
runpodctl gpu list                                    # List available GPUs
runpodctl gpu list --include-unavailable              # Include unavailable GPUs
runpodctl datacenter list                             # List datacenters (alias: dc)
runpodctl billing pods                                # Pod billing history
runpodctl billing serverless                          # Serverless billing history
runpodctl billing network-volume                      # Volume billing history
```

For exact info and billing flags, run `runpodctl <command> --help` or `runpodctl billing <resource> --help`.

### SSH

```bash
runpodctl ssh info <pod-id>                           # Get SSH info (command + key, does not connect)
runpodctl ssh list-keys                               # List SSH keys
runpodctl ssh add-key                                 # Add SSH key
runpodctl ssh remove-key --name <name>                # Remove key by name
runpodctl ssh remove-key --fingerprint <fp>           # Remove key by fingerprint
```

**Remove-key:** if multiple keys share a name, use `--fingerprint` to disambiguate.

**Agent note:** `ssh info` returns connection details, not an interactive session. If interactive SSH is not available, execute commands remotely via `ssh user@host "command"`.

### File Transfer

```bash
runpodctl send <path>                                 # Send file/dir — prints a one-time code
runpodctl receive <code>                              # Receive using that code (positional, no --code flag)
```

`send`/`receive` do encrypted, incremental, compressed transfer — don't pre-tar or
pre-compress the source. **Agent flow (one side sends, the other receives):**

1. Run `send <path>` **without** a code. The **first line of stdout is the one-time
   code**; `send` then blocks until the receiver connects — so capture that first line
   as it streams (background the process, tee to a log) rather than waiting for exit.
2. On the other machine (use `runpodctl ssh` into the pod/host if needed) run
   `receive <code>` with that exact code. Each `send` mints a **fresh** code — never
   reuse or invent one.
3. Both processes must exit `0`. On failure, re-run `send` and use its **new** first-line
   code (don't retry with the old one).

To push local files to a pod: get `ssh info <pod-id>`, start `send` locally (capture the
code), then `ssh` to the pod and run `receive <code>` there. For large/library-style
data, a network volume or the S3 API is often simpler than `send`/`receive`.

### Utilities

```bash
runpodctl doctor                                      # Diagnose and fix CLI issues
runpodctl update                                      # Update CLI
runpodctl version                                     # Show version
runpodctl completion                                  # Auto-detect shell and install completion
```

## URLs

### Pod URLs

Access exposed ports on your pod:

```
https://<pod-id>-<port>.proxy.runpod.net
```

Example: `https://abc123xyz-8888.proxy.runpod.net`

### Serverless URLs

```
https://api.runpod.ai/v2/<endpoint-id>/run        # Async request
https://api.runpod.ai/v2/<endpoint-id>/runsync    # Sync request
https://api.runpod.ai/v2/<endpoint-id>/health     # Health check
https://api.runpod.ai/v2/<endpoint-id>/status/<job-id>  # Job status
```

## Source & docs

- CLI source: https://github.com/runpod/runpodctl
- Releases (binaries): https://github.com/runpod/runpodctl/releases
- Docs: https://docs.runpod.io/runpodctl/overview
