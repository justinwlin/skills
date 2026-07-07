# Golden path 03 — Whisper endpoint (URL → text)

**Goal:** deploy a serverless endpoint that, given an audio URL, returns the
transcription. This is a **serverless** path (request/response, scale-to-zero),
not a pod.

Status: **stub** — to be specified after 01. Likely shape:

- Fastest route: deploy a Whisper worker from the **Runpod Hub**
  (`runpodctl hub search whisper` → `serverless create --hub-id …`), if a
  suitable one exists.
- Custom route: write a handler (`faster-whisper`/`whisper`) that downloads the
  audio URL and transcribes → build an image (`docker build --platform=linux/amd64`)
  → push → create endpoint (MCP or runpodctl). See `runpod-usage/reference/docker.md`.
- Or code-first with **flash** (`@Endpoint` function wrapping Whisper).
- Verify with a real `POST /run` (or `/runsync`) against a sample audio URL and
  assert non-empty text.

Acceptance criteria, chosen route, and gap analysis: TODO.
