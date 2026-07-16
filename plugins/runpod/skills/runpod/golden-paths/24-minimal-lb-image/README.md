# Golden path 24 — minimal serverless **load-balanced** image

✅ **Live-verified** — the minimal load-balanced image is already built and verified end-to-end
in **[golden path 14](../14-load-balancing-endpoint.md)** (stdlib HTTP worker, deployed
`type: "LB"`, `GET /ping` + `POST /echo` + `GET /stats` all returned `200`). This page is the
**image-contract** framing of that path and the counterpart to
[golden path 23 (queue)](../23-minimal-queue-image/README.md) — it does not re-deploy.

## The contrast (this is the point)

Same goal — run your code on serverless — but the **image contract is different**:

| | Queue ([GP23](../23-minimal-queue-image/README.md)) | Load-balanced ([GP14](../14-load-balancing-endpoint.md)) |
| --- | --- | --- |
| You implement | `handler(event)` | a **full HTTP server** |
| Runpod SDK | **yes** — `runpod.serverless.start({"handler": h})` | **none** — no handler, no `runpod` package |
| Container `CMD` | runs the handler loop | runs **your server** (bind `0.0.0.0:$PORT`) |
| Health check | managed by SDK | **you** serve `GET /ping` → `200` |
| Invoke | `POST api.runpod.ai/v2/<id>/runsync` | `POST https://<id>.api.runpod.ai/<your-path>` |
| Endpoint type | default (QB) | **`type: "LB"`** (GraphQL `saveEndpoint` only) |

## The minimal LB image (from GP14, verified)

```python
# app.py — no runpod package, just an HTTP server that answers /ping
import os, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
PORT = int(os.getenv("PORT", "80"))
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ping":
            b = json.dumps({"status": "healthy"}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass
ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
```
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
CMD ["python3", "app.py"]     # runs YOUR server — no handler
```

Two rules the LB contract enforces (full detail + gotchas in
[GP14](../14-load-balancing-endpoint.md)):

1. **Serve `GET /ping`** → `200` healthy / `204` still initializing. The load balancer only
   routes to workers that answer `200`.
2. **Bind the configured port** — all three, or the worker shows `running` but never `ready`:
   (a) set `PORT` on the template; (b) set `PORT_HEALTH` on the template; (c) expose that port.

## When to pick which

- **Queue** — short jobs, guaranteed processing, auto-retry, burst buffering (`/run`,`/runsync`).
- **Load-balanced** — your model's own HTTP server (vLLM/TGI/FastAPI), custom paths/verbs,
  lower single-hop latency, streaming/WebSocket. No queue buffer, no retry (drops on overload).

See [building-images.md → Match the image contract to the target](../../../runpod-usage/reference/building-images.md).
