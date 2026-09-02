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

# 3. 번들이 실제로 실행되는지 확인한다.
#
# bun 은 import/export 가 없는 파일을 CommonJS 로 보고
# `__commonJS(() => { … })` 로 감싸는데, IIFE 번들에는 그것을 호출하는 코드가
# 없어서 본문이 통째로 죽는다. 구문은 멀쩡하고 파일 크기도 그대로라 눈으로는
# 안 보인다. Figma 에는 "실행중" 만 뜨고 창이 열리지 않는다.
#
# 그래서 가짜 figma 객체로 번들을 돌려 showUI 가 실제로 불리는지 본다.
node -e '
const fs = require("fs"), vm = require("vm");
let ui = null;
const figma = {
  showUI: (html) => { ui = html },
  ui: { postMessage: () => {} },
  root: { name: "" },
  clientStorage: { getAsync: async () => null, setAsync: async () => {} },
  on: () => {}, notify: () => {}, closePlugin: () => {},
  currentPage: { selection: [], children: [] },
};
vm.runInContext(fs.readFileSync("dist/plugin.js", "utf8"),
  vm.createContext({ figma, console, setTimeout, clearTimeout, Promise, JSON, Math, Date }),
  { timeout: 5000 });
if (!ui) { console.error("빌드 실패: 번들이 figma.showUI 를 부르지 않는다 (본문이 실행되지 않음)"); process.exit(1) }
if (ui.length < 1000) { console.error("빌드 실패: __html__ 이 비었다"); process.exit(1) }
console.log("확인: showUI 호출, UI " + ui.length + "자");
'

echo "Built dist/plugin.js with inlined UI HTML"
