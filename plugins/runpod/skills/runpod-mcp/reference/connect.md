# Connecting the Runpod MCP server

**Hosted (recommended)** — no API key stored on disk; authenticates with the
"Sign in with Runpod" OAuth flow on first connect:

```bash
# guided installer — detects your agents and configures them
npx @runpod/mcp-server@latest add

# or configure a single client by hand (Claude Code shown)
claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/
```

Prefer your own key over OAuth? Append
`--header "Authorization: Bearer $RUNPOD_API_KEY"` — the server forwards it to the
Runpod API directly.

**Local (stdio)** — runs the server as a subprocess with your key:

```bash
claude mcp add runpod -s user -e RUNPOD_API_KEY=YOUR_KEY -- npx -y @runpod/mcp-server
```

After connecting, reconnect the client (in Claude Code, `/mcp`) and the tools
appear in the session.
