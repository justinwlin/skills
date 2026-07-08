# Golden path 06 — interactive dev pod (SSH / VS Code + persistent /workspace)

**Goal:** from "give me a Runpod dev box I can SSH into / open in VS Code", an
agent provisions a GPU (or CPU) pod on a **PyTorch template** with a **network
volume at `/workspace`**, returns a ready-to-use SSH connection (and a VS Code
Remote-SSH config), and confirms an interactive session works with storage that
**persists across stop/restart**.

Unlike a *service* pod (01/02) there's no HTTP proxy URL to poll and no
`0.0.0.0`-bound server — **success is a live interactive shell/IDE session on a
box whose `/workspace` survives a stop/restart**. It follows the pod development
loop (`../skills/runpod-usage/reference/pod-workflows.md`), stopping at "connect".

Grounded in: `docs/pods/configuration/connect-to-ide.mdx`,
`docs/pods/configuration/use-ssh.mdx`, `runpodctl/SKILL.md`, `storage.md`,
`networking.md`, `../skills/runpod-usage/reference/development-loop.md`.

## Acceptance criteria

1. **Auth** resolved (`export RUNPOD_API_KEY=...`).
2. **SSH key on the account before the pod starts.** The public key must be
   present at boot so it's injected into the pod's `~/.ssh/authorized_keys`; add
   it *after* the pod is running and the pod won't pick it up without a
   redeploy/manual step (see gotcha). Use `runpodctl ssh add-key`.
3. Pod from an **official PyTorch template** (SSH over exposed TCP is
   preconfigured), GPU or CPU per the user's need, with **TCP `22` exposed** and a
   **network volume at `/workspace`**. Use `--stop-after` (keep the box) — not
   `--terminate-after` — for a dev box the user wants to return to.
4. Agent retrieves connection details (`runpodctl ssh info <pod-id>`) and returns
   **both** the ready SSH command and a VS Code / Cursor Remote-SSH `~/.ssh/config`
   block.
5. **Verify interactivity**, not "Running": a non-interactive `ssh <host> 'echo
   ok && nvidia-smi'` (or `uname -a` for CPU) must succeed from outside.
6. Confirm persistence: write a marker to `/workspace`, and note that it survives
   stop/restart while everything outside `/workspace` is wiped.

## Ideal agentic flow (runpodctl lane)

```bash
export RUNPOD_API_KEY=your_key

# 1. Register the SSH key FIRST (must exist before the pod boots to be injected)
runpodctl ssh add-key --key-file ~/.ssh/id_ed25519.pub    # generate one if needed:
#   ssh-keygen -t ed25519 -C "you@example.com"
runpodctl ssh list-keys                                    # confirm it's on the account

# 2. Persistent workspace: a network volume in a DC that has your GPU
runpodctl datacenter list                                  # pick a DC (GPU + volume)
runpodctl network-volume create --name devbox --size 50 --data-center-id <dc>

# 3. Provision — PyTorch template (SSH-over-TCP ready), volume at /workspace,
#    TCP 22 exposed, STOP guard (keep the box), GPU or CPU.
runpodctl template search pytorch                          # official PyTorch template id
runpodctl pod create --name devbox \
  --template-id <runpod-pytorch-template-id> \
  --gpu-id "NVIDIA GeForce RTX 4090" --data-center-ids <dc> \
  --ports "22/tcp" \
  --network-volume-id <volume-id> --volume-mount-path /workspace \
  --ssh --stop-after <iso8601>                             # STOP (keep), not terminate
#   CPU dev box instead: --compute-type cpu --image runpod/pytorch:... (drop --gpu-id)

runpodctl pod get <pod-id>                                 # poll until running
runpodctl ssh info <pod-id>                                 # SSH command + key (TCP form)

# 4. Verify it's actually interactive (not just "Running")
ssh <pod-ssh> 'echo ok && nvidia-smi'                      # CPU: 'echo ok && uname -a'

# 5. Prove /workspace persistence
ssh <pod-ssh> 'echo "hello $(date)" > /workspace/marker.txt && cat /workspace/marker.txt'
#   after a stop/start the file is still there; anything outside /workspace is gone

# 6. Hand off — SSH command + a VS Code / Cursor Remote-SSH config block
#    (use the "SSH over exposed TCP" host/port from `ssh info` — root@<ip> -p <port>)
```

Give the user a `~/.ssh/config` entry so VS Code / Cursor **Remote-SSH: Connect to
Host** works (Command Palette → *Remote-SSH: Connect to Host* → pick the host →
**Open Folder** → `/workspace`):

```
Host runpod-devbox
    HostName <pod-public-ip>
    User root
    Port <external-tcp-port>
    IdentityFile ~/.ssh/id_ed25519
```

## Runpod gotchas this path must respect

- **Key must exist before boot.** Runpod injects your account public key into
  `~/.ssh/authorized_keys` **at pod startup**. Add the key *after* the pod is
  running and it won't be injected — you'd need to redeploy, or paste it via the
  web terminal (`echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys`), a manual step.
  Register the key first (step 1).
- **Only `/workspace` persists.** The network volume at `/workspace` survives
  stop/restart; the container/ephemeral disk (everything else — installed apt
  packages, `/root`, `/tmp`) is **wiped on stop**. Keep code, envs, and data under
  `/workspace` (`storage.md`).
- **Stop vs terminate for a box you keep.** `stop` preserves the pod and its
  `/workspace`; you restart later (you still pay for stopped disk/volume).
  `terminate`/`remove` **deletes** the pod and its volume disk — use it only when
  done for good. For a dev box, guard with `--stop-after`, not `--terminate-after`.
- **TCP port changes on stop/restart.** VS Code Remote-SSH needs **SSH over
  exposed TCP** (a public IP + external port), not the proxied basic-SSH form.
  The external TCP port is **reassigned on every stop/restart** — re-read it from
  `runpodctl ssh info` and update the `~/.ssh/config` `Port` before reconnecting
  (`networking.md`, `use-ssh.mdx`).
- **Basic SSH vs TCP SSH.** The proxied `…@ssh.runpod.io` form works for a shell
  but has no SCP/SFTP and isn't what VS Code Remote-SSH wants — use the
  `root@<ip> -p <port>` (exposed TCP) form for IDE and file transfer. Official
  PyTorch templates support SSH over exposed TCP out of the box.
- **Volume ↔ GPU same DC.** The network volume is DC-locked; place the pod in the
  volume's DC (`storage.md`).
- **"Running" ≠ ready.** The VS Code server / SSH daemon may still be starting —
  verify with a real `ssh <host> 'echo ok'` before handing off; retry briefly if
  the daemon isn't up yet.

## Status: SPEC (not yet live-verified)

Unlike golden paths 01–03 (live-verified), this path has **not** been run end to
end. The flow and gotchas are grounded in `docs/pods/configuration/connect-to-ide.mdx`,
`use-ssh.mdx`, and `runpodctl/SKILL.md`, but the exact `ssh add-key` flag name,
whether `ssh info` surfaces the public-IP/external-port TCP form directly (vs the
Console Connect menu), and the CPU-pod template/image specifics should be
confirmed on a real run before this is marked covered — see gaps below.
