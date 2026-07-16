#!/usr/bin/env bash
# MANUAL RELEASE (break-glass) — cut a tag + GitHub Release using YOUR credentials,
# not the release-please Action's GITHUB_TOKEN. Use this when the org hasn't enabled
# the release-please Action yet (so merging its PR can't tag), or the Action is down.
#
# It stays consistent with release-please: bump-version.sh also updates
# .release-please-manifest.json, so once the Action IS enabled it won't try to
# re-release a version you already cut here.
#
# Normal releases (once the org enables the Action): just merge the release PR — do
# NOT run this. See CONTRIBUTING.md → Cutting a release.
#
# Usage:
#   ./scripts/release.sh X.Y.Z                 # bump + commit + tag + push + GitHub Release
#   ./scripts/release.sh X.Y.Z --publish-only  # tag current HEAD + Release only (bump already merged)
#   ./scripts/release.sh X.Y.Z --dry-run       # show what it would do, change nothing
set -euo pipefail
cd "$(dirname "$0")/.."

NEW="${1:?usage: release.sh <x.y.z> [--publish-only|--dry-run]}"
MODE="${2:-full}"
[[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "error: version must be X.Y.Z, got '$NEW'"; exit 1; }
TAG="v$NEW"
DRY=0; PUBLISH_ONLY=0
case "$MODE" in
  --dry-run) DRY=1 ;;
  --publish-only) PUBLISH_ONLY=1 ;;
  full) ;;
  *) echo "error: unknown mode '$MODE'"; exit 1 ;;
esac
ASSUME_YES=0; for a in "$@"; do [ "$a" = "--yes" ] && ASSUME_YES=1; done
run() { echo "+ $*"; [ "$DRY" = 1 ] || "$@"; }

# Confirmation gate — this pushes tags/commits and creates a GitHub Release on origin
# (github.com/runpod/skills) as YOU. --dry-run and --yes skip the prompt.
confirm() {
  [ "$DRY" = 1 ] && return 0
  [ "$ASSUME_YES" = 1 ] && return 0
  echo "About to release $TAG on origin ($(git remote get-url origin)) as $(gh api user -q .login 2>/dev/null || echo you):"
  echo "  mode=$MODE — will push $([ "$PUBLISH_ONLY" = 0 ] && echo 'a release commit + ')the tag $TAG and create a GitHub Release."
  read -r -p "Continue? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "aborted — nothing pushed"; exit 1; }
}

# --- Guards ---
command -v gh >/dev/null || { echo "error: gh CLI not found"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "error: 'gh auth login' first (this releases as YOU)"; exit 1; }
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "main" ] || echo "warning: on '$BRANCH', not 'main' — tagging this HEAD anyway"
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then echo "error: tag $TAG already exists"; exit 1; fi
if git ls-remote --exit-code --tags origin "$TAG" >/dev/null 2>&1; then echo "error: tag $TAG exists on origin"; exit 1; fi

confirm

# --- Bump (skipped in --publish-only, where the bump already landed on main) ---
if [ "$PUBLISH_ONLY" = 0 ]; then
  [ "$DRY" = 1 ] || [ -z "$(git status --porcelain)" ] || { echo "error: working tree not clean — commit/stash first"; exit 1; }
  run ./scripts/bump-version.sh "$NEW"
  echo "+ (edit the CHANGELOG '_describe changes_' line now if you want richer notes)"
  run python3 hooks/check_versions.py
  run git commit -aqm "chore(release): $TAG"
  run git push origin HEAD
else
  # Publish-only: the version files must already be at NEW (bump merged via PR).
  run python3 hooks/check_versions.py
  CUR="$(cat version.txt 2>/dev/null | tr -d '[:space:]')"
  [ "$DRY" = 1 ] || [ "$CUR" = "$NEW" ] || { echo "error: version.txt is '$CUR', not '$NEW' — did the bump merge to main?"; exit 1; }
fi

# --- Tag + push + GitHub Release (the part the blocked Action can't do) ---
run git tag -a "$TAG" -m "$TAG"
run git push origin "$TAG"

# Release notes: the CHANGELOG section for this version, else a stub.
NOTES="$(awk -v v="## $NEW" '$0 ~ v {f=1; next} /^## / && f {exit} f' plugins/runpod/CHANGELOG.md 2>/dev/null)"
[ -n "$NOTES" ] || NOTES="Release $TAG"
if [ "$DRY" = 1 ]; then
  echo "+ gh release create $TAG --title $TAG --notes <<CHANGELOG section>>"
  printf '%s\n' "--- notes preview ---" "$NOTES" "---------------------"
else
  printf '%s\n' "$NOTES" | gh release create "$TAG" --title "$TAG" --notes-file -
fi
echo "Done: $TAG tagged + released as $(gh api user -q .login 2>/dev/null || echo you)."
