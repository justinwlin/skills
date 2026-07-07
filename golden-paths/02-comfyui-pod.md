# Golden path 02 — ComfyUI server on a pod + access URL

**Goal:** stand up a ComfyUI server on a Runpod pod and return a working URL to
the web UI.

Status: **stub** — to be specified after 01 lands. Shares 01's shape (pod +
exposed HTTP port + SSH-exec install + readiness poll + volume for models), with
ComfyUI specifics:

- Expose ComfyUI's port (default `8188/http`) at creation; bind to `0.0.0.0`
  (`--listen 0.0.0.0`).
- Install into the PyTorch template (or a ComfyUI image); manage Python deps with
  `uv`; put models/custom nodes on a **network volume** so they persist.
- Poll `https://<pod-id>-8188.proxy.runpod.net` until the UI responds.
- Note: the UI is public via the proxy and unauthenticated — warn the user.

Acceptance criteria, full flow, and gap analysis: TODO.
