#!/bin/bash
# Build Figma plugin: compile TS + inline UI HTML into plugin.js
set -e
cd "$(dirname "$0")"

# 1. Compile TypeScript
bun build src/plugin.ts --outdir=dist --target=browser --format=iife 2>&1

# 2. Read UI HTML and escape for JS string
UI_HTML=$(cat src/ui.html)

# 3. Inject __html__ definition at the top of the IIFE
# Replace the first occurrence of figma.showUI(__html__ with the inlined version
sed -i '' "1s|^|var __html__ = \`$(echo "$UI_HTML" | sed 's/`/\\`/g' | sed 's/\$/\\$/g' | tr '\n' ' ')\`;\n|" dist/plugin.js

echo "Built dist/plugin.js with inlined UI HTML"
