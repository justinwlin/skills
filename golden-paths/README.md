# Golden paths

End-to-end tasks an agent should be able to complete **start to finish** using
the Runpod skills — the yardstick for "can it actually do everything agentically."
Each file is a spec: the goal, testable acceptance criteria, the ideal agentic
flow, Runpod gotchas, and a gap analysis (how far the current skills are from it).

These are agent-facing acceptance scenarios, not marketing demos. An agent —
not a human clicking the Console — must be able to complete them.

| # | Golden path | Status |
| --- | --- | --- |
| 01 | [Ollama server on a pod + access URL](01-ollama-pod.md) | **covered** — live-verified 2026-07-07 |
| 02 | [ComfyUI server on a pod + access URL](02-comfyui-pod.md) | **covered** — live-verified 2026-07-07 |
| 03 | [Whisper endpoint (URL → text)](03-whisper-endpoint.md) | **covered** — live-verified 2026-07-07 |
| 04 | [LoRA fine-tune (training run) on a pod](04-finetune-pod.md) | **spec** (not yet live-verified) |
| 05 | [Custom model → serverless endpoint (cross-lane pipeline)](05-model-to-endpoint-pipeline.md) | **spec** (not yet live-verified) |
| 06 | [Interactive dev pod (SSH / VS Code + persistent /workspace)](06-dev-pod.md) | **spec** (not yet live-verified) |

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
