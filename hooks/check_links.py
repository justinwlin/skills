#!/usr/bin/env python3
"""Verify every relative Markdown link in the repo resolves to a real file.

Skips http(s)/mailto/anchor-only links; strips #anchors before checking the path.
Run from the repo root: python3 hooks/check_links.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\]\(([^)]+)\)")

bad = []
for md in ROOT.rglob("*.md"):
    if ".git" in md.parts:
        continue
    d = md.parent
    for line_no, line in enumerate(md.read_text(errors="replace").splitlines(), 1):
        for m in LINK.finditer(line):
            link = m.group(1).strip()
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = link.split("#", 1)[0]
            if not path:
                continue
            target = (d / path).resolve()
            if not target.exists():
                bad.append((md.relative_to(ROOT), line_no, link))

if bad:
    print("link check FAILED — broken relative links:")
    for path, ln, link in bad:
        print(f"  - {path}:{ln}  ->  {link}")
    sys.exit(1)

print("link check OK")
