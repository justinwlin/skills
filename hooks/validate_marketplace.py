#!/usr/bin/env python3
"""Validate the plugin marketplace manifests and their referenced paths.

Checks, statically (no network, no harness):
  - .claude-plugin/marketplace.json parses and has name + plugins.
  - Each plugin's source dir exists under metadata.pluginRoot (default ./plugins).
  - Each plugin has a .claude-plugin/plugin.json that parses.
  - Every skills[] path resolves to a dir containing a SKILL.md.
  - A plugin .mcp.json (if present) parses.
  - .agents/plugins/marketplace.json (Codex, if present) parses and its plugin
    source paths exist.

Exit non-zero on any failure. Run from the repo root: python3 hooks/validate_marketplace.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors = []


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        errors.append(f"missing file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as e:
        errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {e}")
    return None


def check_claude_marketplace():
    mp = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    if mp is None:
        return
    if not mp.get("name"):
        errors.append(".claude-plugin/marketplace.json: missing 'name'")
    plugins = mp.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(".claude-plugin/marketplace.json: 'plugins' must be a non-empty list")
        return
    plugin_root = ROOT / mp.get("metadata", {}).get("pluginRoot", "./plugins")
    for p in plugins:
        name = p.get("name", "<unnamed>")
        source = p.get("source")
        if not source:
            errors.append(f"plugin '{name}': missing 'source'")
            continue
        pdir = (plugin_root / source).resolve()
        if not pdir.is_dir():
            errors.append(f"plugin '{name}': source dir not found: {pdir.relative_to(ROOT)}")
            continue
        # per-plugin manifest
        load_json(pdir / ".claude-plugin" / "plugin.json")
        # bundled MCP config, if any
        mcp = pdir / ".mcp.json"
        if mcp.exists():
            load_json(mcp)
        # declared skills
        for sk in p.get("skills", []):
            sdir = (pdir / sk).resolve()
            if not sdir.is_dir():
                errors.append(f"plugin '{name}': skill path not found: {sk}")
            elif not (sdir / "SKILL.md").is_file():
                errors.append(f"plugin '{name}': no SKILL.md in {sk}")


def check_codex_marketplace():
    path = ROOT / ".agents" / "plugins" / "marketplace.json"
    if not path.exists():
        return  # Codex support is optional
    mp = load_json(path)
    if mp is None:
        return
    for p in mp.get("plugins", []):
        src = p.get("source", {})
        rel = src.get("path")
        if not rel:
            errors.append(f"codex plugin '{p.get('name')}': missing source.path")
            continue
        if not (ROOT / rel).is_dir():
            errors.append(f"codex plugin '{p.get('name')}': path not found: {rel}")


def main():
    check_claude_marketplace()
    check_codex_marketplace()
    if errors:
        print("marketplace validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("marketplace validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
