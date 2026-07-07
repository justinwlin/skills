# On-pod setup & install hygiene

How to install and configure software on a pod so it is reproducible, survives
restarts, and doesn't wedge on an interactive prompt. Applies to any workload;
run these over the SSH channel from the pod development loop (`pod-workflows.md`).

## Use package managers, not ad-hoc downloads

- **System packages → `apt`** (Debian/Ubuntu base images):
  ```bash
  DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y <pkgs>
  ```
- **Python → `uv`** (fast, reproducible, one static binary). Prefer it over bare
  `pip`/`conda`:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  uv venv /workspace/.venv && . /workspace/.venv/bin/activate
  uv pip install <packages>            # or: uv pip install -r requirements.txt
  ```
  `uv` resolves and installs far faster than pip and avoids most dependency
  conflicts. Put the venv on the volume (`/workspace/...`) so it persists.
- **A vendor install script** (e.g. a service's official `install.sh`) is fine
  when that is the supported path — just pin a version if the script allows.

## Make it non-interactive

An agent can't answer prompts. Always:

- Pass `-y` / `--yes`; set `DEBIAN_FRONTEND=noninteractive` for apt.
- Provide required config via env vars or flags, not TTY prompts.
- Avoid commands that open a pager or editor.

## Pin versions

- Pin package and image versions (`pkg==1.2.3`, `image:tag`, not `latest`) so a
  rebuild or restart reproduces the same environment. See `gotchas.md`.

## Persist heavy artifacts on the volume

Anything large or slow to fetch goes on the network volume so it survives restarts
and isn't re-downloaded (see `storage.md`). Point caches at the volume:

```bash
export HF_HOME=/workspace/hf-cache          # HuggingFace models/datasets
export UV_CACHE_DIR=/workspace/uv-cache      # uv package cache
export PIP_CACHE_DIR=/workspace/pip-cache
```

## Run long work in the background, and log

Installs, model pulls, and servers can outlast a single SSH command. Background
them and log to the volume so you can poll progress and diagnose later:

```bash
ssh <host> '(long-running-setup > /workspace/setup.log 2>&1 &) '
ssh <host> 'tail -n 20 /workspace/setup.log'   # poll
```

## Be idempotent

Write setup so re-running it is safe (check-before-install, `mkdir -p`, `|| true`
on best-effort steps). You will run it again after a restart or a fix.

## Verify each step

Check the exit code / expected output of each install before moving on, rather
than chaining everything and discovering a failure at the end. Surface the actual
error; don't swallow it.
