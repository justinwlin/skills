# Golden paths

End-to-end tasks an agent should be able to complete **start to finish** using
the Runpod skills — the yardstick for "can it actually do everything agentically."
Each file is a spec: the goal, testable acceptance criteria, the ideal agentic
flow, Runpod gotchas, and a gap analysis (how far the current skills are from it).

These are agent-facing acceptance scenarios, not marketing demos. An agent —
not a human clicking the Console — must be able to complete them.

## Table of contents

Some paths have **more than one way to get there** (a fast prebuilt route and a
from-scratch route). Those variants are listed as sub-rows so you can jump straight
to the approach you want.

| # | Golden path | Kind | Approach(es) | Status |
| --- | --- | --- | --- | --- |
| 01 | [Ollama server on a pod + URL](01-ollama-pod.md) | pod / server | runpodctl pod + SSH | ✅ live-verified |
| 02 | [ComfyUI server on a pod + URL](02-comfyui-pod.md) | pod / server | — | ✅ live-verified |
| | ↳ [Variant A — from scratch](02-comfyui-pod.md#variant-a--from-scratch-on-a-pytorch-template-runpodctl-lane) | | PyTorch template + install | ✅ |
| | ↳ [Variant B — prebuilt official image](02-comfyui-pod.md#variant-b--prebuilt-official-image-faster) | | official template (auto-starts) | ✅ (faster) |
| 03 | [Whisper endpoint (audio → text)](03-whisper-endpoint.md) | serverless | — | ✅ live-verified |
| | ↳ [Variant A — Runpod Hub worker](03-whisper-endpoint.md#variant-a--runpod-hub-worker-recommended) | | runpodctl + Hub (recommended) | ✅ |
| | ↳ [Variant B — from scratch with flash](03-whisper-endpoint.md#variant-b--build-from-scratch-with-flash) | | flash code-first handler | ✅ |
| 04 | [LoRA fine-tune (training run) on a pod](04-finetune-pod.md) | pod / batch job | runpodctl pod + volume | ⚠️ spec |
| 05 | [Custom model → serverless endpoint](05-model-to-endpoint-pipeline.md) | cross-lane pipeline | hf → docker → runpodctl | ⚠️ spec |
| 06 | [Interactive dev pod (SSH / VS Code)](06-dev-pod.md) | pod / interactive | runpodctl pod + volume | ⚠️ spec |

> **When there are two variants, prefer the prebuilt/Hub one** (Variant B for
> ComfyUI, Variant A for Whisper) unless you need custom code — that's the
> development loop's "prefer prebuilt over from-scratch" rule in action.

> **01–03 are live-verified** (run end to end on a real account). **04–06 are
> specs awaiting a run** — grounded in the skills + docs, but not yet executed, so
> exact flags/paths may need confirming (each file lists what to verify).

## Status legend

- **stub** — goal captured, not yet specified.
- **drafted — gaps identified** — flow + acceptance criteria written; skill gaps listed.
- **spec (not yet live-verified)** — full flow, acceptance criteria, and gotchas
  written and grounded in the skills + docs, but **not yet run** end to end;
  exact flags/paths still need confirming on a real account.
- **covered** — the skills contain everything an agent needs; verified by a run.

## Cross-cutting requirements (every path)

1. **Auth** — resolve `RUNPOD_API_KEY` (or `runpodctl doctor` / MCP OAuth) before acting.
2. **Agentic execution** — an agent has no Console/web terminal; it must drive
   everything through the CLI/API/MCP and SSH-exec, non-interactively.
3. **Readiness, not fire-and-forget** — poll until the service actually answers;
   don't report success on "pod Running" alone.
4. **Escalate on manual steps** — if something needs a human (OAuth, a quota
   increase, a license click, a missing credential), stop and tell the user.
5. **Clean up** — set `--stop-after` / `--terminate-after` on test resources.
