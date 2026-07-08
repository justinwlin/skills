# Changelog

All notable changes to the `runpod` plugin are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## 1.0.0

Initial release as a plugin.

- Router (`runpod`) + lanes: `runpod-mcp`, `runpodctl`, `flash`, `companion-clis`,
  `runpod-usage` (concepts + `reference/*.md`).
- Bundled hosted Runpod MCP server config (`.mcp.json`).
- Worked golden paths (Ollama, ComfyUI, Whisper live-verified; fine-tune,
  model→endpoint pipeline, dev pod as specs).
- Evals per lane; the golden development loop and pod/serverless sub-loops.
