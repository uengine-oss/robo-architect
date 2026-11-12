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
# every newline. `JSON.stringify` gives a correctly escaped JS string literal
# for any input, so the file stays byte-exact.
#
# ⚠ 이 단계는 **node** 로 한다(전에는 python 이었다). 이 스크립트가 2026-11-12 부터
#   `docker/Dockerfile.web` 안에서도 돌고(웹 판이 플러그인 묶음을 내려 준다), 그
#   빌드 이미지 `node:22-bookworm-slim` 에는 **python 이 없다**. 아래 3단계가 이미
#   node 를 쓰므로 의존을 하나로 줄인다.
node -e '
const fs = require("fs");
const html = JSON.stringify(fs.readFileSync("src/ui.html", "utf8"));
fs.writeFileSync("dist/plugin.js",
  "var __html__ = " + html + ";\n" + fs.readFileSync("dist/plugin.js", "utf8"));
'

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
