# Golden paths

End-to-end tasks an agent should be able to complete **start to finish** using
the Runpod skills — the yardstick for "can it actually do everything agentically",
and a worked reference to copy from.

These are agent-facing scenarios, not marketing demos. An agent — not a human
clicking the Console — must be able to complete them. **01–03 were run live on a
real account** (each caught real skill bugs we then fixed); **04–06 are specs**
grounded in the skills + docs but not yet executed.

## Layout

- A path with **one approach** is a single file: `NN-name.md`.
- A path with **multiple approaches** is a folder: `NN-name/` with a `README.md`
  (goal, "which variant?", shared schema/gotchas/cost) plus one file per variant.

Each doc follows the same template: **Goal · Status · Lane(s) → When to use →
Prerequisites → Walkthrough (real commands) → Verify it works (the actual test +
observed output) → Gotchas we hit → Cost & cleanup → Skill gaps folded back.**

## Table of contents

| # | Golden path | Kind | Approach(es) | Status |
| --- | --- | --- | --- | --- |
| 01 | [Ollama server on a pod + URL](01-ollama-pod.md) | pod / server | runpodctl pod + SSH | ✅ live-verified |
| 02 | [ComfyUI server on a pod + URL](02-comfyui-pod/README.md) | pod / server | — | ✅ live-verified |
| | ↳ [Variant A — from scratch](02-comfyui-pod/variant-a-from-scratch.md) | | PyTorch template + install | ✅ |
| | ↳ [Variant B — prebuilt official image](02-comfyui-pod/variant-b-prebuilt.md) | | official template (auto-starts) | ✅ (faster) |
| 03 | [Whisper endpoint (audio → text)](03-whisper-endpoint/README.md) | serverless | — | ✅ live-verified |
| | ↳ [Variant A — Runpod Hub worker](03-whisper-endpoint/variant-a-hub.md) | | runpodctl + Hub (recommended) | ✅ |
| | ↳ [Variant B — from scratch with flash](03-whisper-endpoint/variant-b-flash.md) | | flash code-first handler | ✅ |
| 04 | [LoRA fine-tune (training run) on a pod](04-finetune-pod.md) | pod / batch job | runpodctl pod + volume | ⚠️ spec |
| 05 | [Custom model → serverless endpoint](05-model-to-endpoint-pipeline.md) | cross-lane pipeline | hf → docker → runpodctl | ⚠️ spec |
| 06 | [Interactive dev pod (SSH / VS Code)](06-dev-pod.md) | pod / interactive | runpodctl pod + volume | ⚠️ spec |
| 07 | [Network-volume handoff (pod → volume → serverless)](07-network-volume-handoff.md) | pod + serverless | runpodctl + flash | ✅ live-verified |

> **When a path has two variants, prefer the prebuilt/Hub one** (Variant B for
> ComfyUI, Variant A for Whisper) unless you need custom code — that's the
> development loop's "prefer prebuilt over from-scratch" rule in action.

## How to use these

1. **Match your task to a row** in the table (or read
   [`../skills/runpod-usage/reference/development-loop.md`](../skills/runpod-usage/reference/development-loop.md)
   first if you're unsure whether it's a pod or a serverless job).
2. **For a multi-variant path, open the folder `README.md` first** — it tells you
   which variant to pick and holds the shared schema/gotchas/cost. Then open the
   variant file for the step-by-step.
3. **Check the Status before you trust it.** ✅ live-verified paths were run end to
   end — commands and outputs are real. ⚠️ spec paths are reasoned from the docs,
   **not proven**; treat their exact flags/paths as unconfirmed (each file lists
   what a real run should verify).
4. **Follow the Walkthrough, then actually run Verify** — "Running" ≠ "ready".
   Don't report success until the service answers a real request.
5. **If the skills fall short, fold the fix back** into the relevant `SKILL.md` /
   `reference/*.md` — that's how a live run improves the skills (see each path's
   "skill gaps folded back" section for examples).

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
