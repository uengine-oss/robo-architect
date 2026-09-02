#!/bin/bash
# Build Figma plugin: compile TS + inline UI HTML into plugin.js
set -e
cd "$(dirname "$0")"

# 1. Compile TypeScript
bun build src/plugin.ts --outdir=dist --target=browser --format=iife 2>&1

# 2. Prepend the UI as `__html__`.
#
# This used to be a `sed 's|^|…|'` over the whole HTML. The HTML is the
# replacement text there, so a single `|` anywhere in it — a regex alternation,
# a table border, a JS or — closed the substitution early and sed died with
# "bad flag in substitute command". It also mangled backslashes and collapsed
# every newline. Doing the escaping in Python keeps the file byte-exact.
python3 - <<'PY'
import json, pathlib
dist = pathlib.Path("dist/plugin.js")
html = pathlib.Path("src/ui.html").read_text(encoding="utf-8")
# json.dumps gives a correctly escaped JS string literal for any input.
dist.write_text(f"var __html__ = {json.dumps(html)};\n" + dist.read_text(encoding="utf-8"),
                encoding="utf-8")
PY

echo "Built dist/plugin.js with inlined UI HTML"
