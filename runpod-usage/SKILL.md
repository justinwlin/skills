---
name: runpod-usage
description: >-
  Conceptual reference for how Runpod works — pods vs serverless, workers and cold
  starts, building a Runpod-compatible Docker image, container disk vs network
  volumes and S3 access, GPU/VRAM selection and pricing, pod/endpoint URLs, and
  common gotchas. Use to answer "how does X work", "which GPU", or "how do I build
  a container for Runpod". Not a tool — for actions use runpodctl, runpod-mcp, or
  flash.
metadata:
  author: runpod
  version: "1.0"
license: Apache-2.0
---

# Runpod usage (concepts)

Background knowledge for making the right choice before you act. This skill runs
nothing — once you know what to do, execute with **runpod-mcp**/**runpodctl**
(infra), **flash** (your own code), or **companion-clis** (models/images/data).

Read the one reference file that matches the question:

| Question | Read |
| --- | --- |
| Pods vs serverless, workers, cold starts, FlashBoot, queue vs load-balanced | `reference/concepts.md` |
| Build a Docker image Runpod can run (handler contract, Dockerfile, `--platform=linux/amd64`) | `reference/docker.md` |
| Where data lives — container disk vs network volume, model caching, S3 access | `reference/storage.md` |
| Which GPU / how much VRAM / cost & availability / data centers | `reference/gpu-selection.md` |
| Reaching a pod or endpoint over HTTP (proxy URLs, exposed ports) | `reference/networking.md` |
| Common mistakes and how to avoid them | `reference/gotchas.md` |
