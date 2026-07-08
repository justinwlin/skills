# Contributing

This repo is a **plugin marketplace**. It ships one plugin, `runpod`, whose skills
also install via [skills.sh](https://skills.sh/) — both read the same
`.claude-plugin/marketplace.json`.

## Layout

```
.claude-plugin/marketplace.json   Claude Code / skills.sh manifest (lists the plugin + its skills)
.agents/plugins/marketplace.json  Codex manifest
plugins/runpod/
  .claude-plugin/plugin.json      Claude Code plugin manifest
  .codex-plugin/plugin.json       Codex plugin manifest
  gemini-extension.json           Gemini manifest (contextFileName: README.md)
  .mcp.json                       hosted Runpod MCP server config
  README.md  CHANGELOG.md
  skills/<name>/SKILL.md          the skills (+ reference/, evals/)
  golden-paths/                   worked end-to-end reference tasks (no SKILL.md)
hooks/                            validation scripts
```

## Adding or changing a skill

1. Edit or add `plugins/runpod/skills/<name>/SKILL.md` (YAML frontmatter needs
   `name` + `description`; keep the body small and push detail into `reference/*.md`).
2. If you **add** a skill, list its path in the `skills` array of both
   `.claude-plugin/marketplace.json` and (for Codex) confirm it lives under the
   plugin's `skills/` dir.
3. Add or update an `evals/*.eval.md` when you change routing or behavior.
4. Bump `plugins/runpod/CHANGELOG.md` + the `version` in the plugin manifests
   ([semver](https://semver.org/)).

## Conventions

- **Spelling:** "Runpod" (capital R). The CLI command is `runpodctl` (lowercase).
- **Skills/commands are named as verbs; agents as role-nouns.**
- **License:** Apache-2.0.
- **Auth:** everything unifies on `RUNPOD_API_KEY`; the hosted MCP is the
  exception (OAuth). Companion CLIs use their own creds.

## Validate before pushing

```bash
python3 hooks/validate_marketplace.py     # manifests + referenced paths resolve
python3 hooks/check_runpod_branding.py     # "Runpod" casing
python3 hooks/check_links.py               # relative Markdown links resolve
```

Then smoke-test the two install paths on your branch:

```bash
# Plugin (Claude Code): add the local dir as a marketplace, then install
/plugin marketplace add ./
/plugin install runpod@runpod

# skills.sh
npx skills add ./
```
