# Getting started (auth & first-run setup)

Before any lane can act, its credential has to resolve. Everything Runpod-side
uses **one key**, `RUNPOD_API_KEY`; the companion CLIs use their own. Do the setup
for the lane you're about to use, then follow the development loop.

## The Runpod API key

Get it once at **https://runpod.io/console/user/settings** → API Keys. Then make
it resolvable for the lane:

| Lane | Set the key | Notes |
| --- | --- | --- |
| **runpodctl** | `export RUNPOD_API_KEY=...` | Non-interactive — runpodctl reads it. Best for agents/CI/scripts. |
| runpodctl (human) | `runpodctl doctor` | Interactive; stores the key **and** sets up SSH keys. Prompts, so not for agents. |
| **flash** | `export RUNPOD_API_KEY=...` | Or `flash login` (browser OAuth) for a human. |
| **runpod-mcp (hosted)** | "Sign in with Runpod" OAuth on first connect | No key on disk. Or pass `Authorization: Bearer $RUNPOD_API_KEY`. |
| **runpod-mcp (local)** | `RUNPOD_API_KEY` env in the MCP client config | Forwarded to the API. |

Agent rule: **`export RUNPOD_API_KEY=...` is the universal non-interactive path**
(runpodctl and flash both honor it). Avoid `runpodctl doctor` in automation — it
prompts.

## SSH (only needed for pods you exec into)

Pods created with `--ssh` (the runpodctl default) are reachable once you have a key
registered:

- A human's easiest path: `runpodctl doctor` registers an SSH key for you.
- Get connection details for a specific pod: `runpodctl ssh info <pod-id>` (prints
  the ssh command + key path; does not connect).
- Agents connect non-interactively:
  `ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p <port> root@<host> 'cmd'`.

Serverless endpoints need no SSH.

## Companion CLI credentials (separate from RUNPOD_API_KEY)

Do NOT reuse the Runpod key for these — each has its own (see the `companion-clis`
skill for details):

- **`hf`** — HuggingFace token (`hf auth login`); read scope to pull, write to push.
- **`docker`** — Docker Hub PAT (`docker login`).
- **`gh`** — GitHub auth (`gh auth login`).
- **`aws`** — Runpod **S3** keys (user id `user_…` + S3 API key `rps_…`), with
  `--region <dc> --endpoint-url https://s3api-<dc>.runpod.io/`. NOT AWS creds, NOT
  the Runpod API key.

## Verify you're set up

```bash
export RUNPOD_API_KEY=...
runpodctl user            # prints your account (confirms the key works)
runpodctl gpu list        # confirms API access
```

Then pick your workload and follow `development-loop.md`.
