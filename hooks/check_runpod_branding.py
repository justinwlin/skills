#!/usr/bin/env python3
"""Enforce Runpod branding: the word is "Runpod", never "RunPod" or "RUNPOD".

Scans tracked Markdown files for the wrong casing. Env var names and code
identifiers legitimately use ALL-CAPS (e.g. RUNPOD_API_KEY, RUNPOD_ASSISTANT_*),
so uppercase forms immediately followed by `_` or attached to `CTL`/`.io` are
ignored. Exit non-zero if any bad occurrence is found.

Run from the repo root: python3 hooks/check_runpod_branding.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# "RunPod" (camel) always wrong; "RUNPOD" wrong unless part of an ENV_VAR token.
CAMEL = re.compile(r"RunPod")
UPPER = re.compile(r"RUNPOD(?![_A-Z0-9.])")

bad = []
for md in ROOT.rglob("*.md"):
    if ".git" in md.parts:
        continue
    for i, line in enumerate(md.read_text(errors="replace").splitlines(), 1):
        for m in CAMEL.finditer(line):
            bad.append((md.relative_to(ROOT), i, "RunPod", line.strip()))
        for m in UPPER.finditer(line):
            bad.append((md.relative_to(ROOT), i, "RUNPOD", line.strip()))

if bad:
    print('branding check FAILED — use "Runpod" (not "RunPod"/"RUNPOD"):')
    for path, ln, tok, text in bad:
        print(f"  - {path}:{ln}  [{tok}]  {text[:100]}")
    sys.exit(1)

print("branding check OK")
