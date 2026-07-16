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
4. To ship the change, cut a release (see **Cutting a release** below) — don't bump
   the manifests by hand.

## Conventions

- **Spelling:** "Runpod" (capital R). The CLI command is `runpodctl` (lowercase).
- **Skills/commands are named as verbs; agents as role-nouns.**
- **License:** Apache-2.0.
- **Auth:** everything unifies on `RUNPOD_API_KEY`; the hosted MCP is the
  exception (OAuth). Companion CLIs use their own creds.

## Commit messages

Every commit to `main` **must** be a [Conventional Commit](https://www.conventionalcommits.org/)
— the release bot reads these to decide the next version and to write the CHANGELOG. Format:

```
<type>(<optional scope>): <summary>

<optional body>

<optional footer, e.g. BREAKING CHANGE: …>
```

**Type → what it does at release time:**

| Type | Meaning | Version effect | In CHANGELOG? |
| --- | --- | --- | --- |
| `feat` | a new capability | **minor** bump (1.0.0 → 1.1.0) | ✅ Features |
| `fix` | a bug fix | **patch** bump (1.0.0 → 1.0.1) | ✅ Bug Fixes |
| `perf` | performance improvement | no bump | ✅ Performance |
| `refactor` | code change, no feat/fix | no bump | ✅ Refactors |
| `docs` | docs only | no bump | ✅ Documentation |
| `revert` | reverts a prior commit | no bump | ✅ Reverts |
| `chore` | tooling/deps/housekeeping | no bump | hidden |
| `style` | formatting only | no bump | hidden |
| `test` | tests only | no bump | hidden |
| `build` | build system | no bump | hidden |
| `ci` | CI config | no bump | hidden |

**Breaking changes** (any type): add `!` after the type (`feat!:`) **or** a
`BREAKING CHANGE: …` footer → **major** bump (1.0.0 → 2.0.0).

- **Scope** (optional) narrows the area: `feat(runpodctl): …`, `fix(flash): …`, `docs(golden-paths): …`.
- A release fires only when there's at least one `feat`/`fix`/breaking since the last release;
  a batch of pure `docs`/`chore` won't cut a version on its own (they still ride along in the
  next release's CHANGELOG). Which types show vs. hide is set by `changelog-sections` in
  `release-please-config.json` — flip any `hidden` there if you want it surfaced.
- Examples: `feat(runpod-mcp): add worker-log streaming note` · `fix(flash): correct empty-input rule` ·
  `docs: clarify auth in the router` · `feat!: require RUNPOD_API_KEY for all lanes`.

## Cutting a release

**Releases are automated with [release-please](https://github.com/googleapis/release-please) — you never bump a version by hand.** Write the [Conventional Commits](#commit-messages) above and the bot does the rest.

release-please runs on every push to `main` (`.github/workflows/release-please.yml`) and maintains a **standing release PR** — think of it as a bot that keeps **absorbing every releasable commit since the last release** into one accumulating PR, continuously updating the pending version + CHANGELOG preview. You don't touch it until you're ready to ship; then you **merge it**, which tags the release `vX.Y.Z` and resets the cycle. That merge is the only manual step — a deliberate ship gate, not hand-editing.

**One version for the whole plugin, kept in lockstep.** release-please writes the same semver to every version-bearing file at once (config: `release-please-config.json`, current version tracked in `.release-please-manifest.json` + `version.txt`):

- the two `plugin.json`s, `gemini-extension.json`, top-level `marketplace.json` (via the JSON `jsonpath` updater),
- each skill's `SKILL.md` `metadata.version` (via the `# x-release-please-version` annotation on that line) — there is **no** independent per-skill versioning; a skill's version just mirrors the plugin version so a reader of any single `SKILL.md` sees which release it shipped in.

`hooks/check_versions.py` runs in CI as a drift guard and **fails the build if any of these disagree**. `scripts/bump-version.sh` does the same bump locally but is an **emergency/local fallback only** — normal releases go through release-please.

Don't add a `version` to the plugin *entry* inside `marketplace.json`'s `plugins[]` — a `plugin.json` vs entry mismatch silently masks updates. And don't remove the `# x-release-please-version` annotation from a `SKILL.md` version line, or release-please will stop bumping that skill.

## Validate before pushing

```bash
python3 hooks/validate_marketplace.py     # manifests + referenced paths resolve
python3 hooks/check_versions.py            # all manifests declare the same version
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
