#!/usr/bin/env python3
"""Extract the user-visible Korean UI text of Robo Architect Lite for the English mode
(desktop/i18n/strings.json, desktop/i18n/missing.txt).

The app hardcodes Korean almost everywhere; English mode translates what reaches the screen through
one dictionary, desktop/resources/i18n/ko-en.json, using desktop/resources/i18n/translate.js (the
same translator as Ontological Studio's desktop; main/lang.ts injects both into every page). This
script finds the Korean that can reach a screen and checks it against that dictionary:

  desktop/i18n/strings.json  every extracted string — "exact" (a whole text node / attribute /
                             message) or "pattern" (built from variables; each variable part is {0},
                             {1}, …) — with the source group and file:line, plus what the skip rules
                             left out
  desktop/i18n/missing.txt   extracted but not translated by the dictionary (the same check
                             translate.js runs at runtime). Entries that were not in the previous
                             strings.json are marked [new], so a rerun after code changes shows what
                             to add.

  python3 desktop/scripts/i18n-extract.py            # rerun after any source change
  python3 desktop/scripts/i18n-extract.py --check    # same, exit 1 when something is missing
  python3 desktop/scripts/i18n-extract.py --json-missing out.json   # missing entries as JSON (to translate)

Sources (groups):
  frontend   frontend/src — the Robo Architect SPA every tab runs
  analyzer   robo-analyzer/robo-data-frontend/src — only what Lite's Legacy tab can reach: the import
             closure of the remote (src/bootstrap.ts), where src/app/config/features.ts contributes only
             the EMBEDDED features (embeddable: true — code · data sources · code graph · data schema)
  shell      desktop/resources/shell — the window shell (tab strip + home)
  main       desktop/src/main — the Electron main process (menus, messages it hands to the shell)
  backend    api/ — only the messages the UI shows (interview questions, progress phases, HTTP error
             details …), see BACKEND_* below; prompts and logs are left out

JS / Vue / TS sources are parsed with Babel and the Vue SFC compiler from frontend/node_modules
(present after `npm install` in frontend), driven by a small Node helper embedded below. Python
sources are parsed with the ast module.

What becomes an entry:
  - Vue template text: consecutive text and {{ }} in one element form one text node (Vue renders
    them as one); child elements split it ("총 <b>{{n}}</b>건" → "총" and "건").
  - static attributes and bound attribute / directive expressions in templates
  - string literals and template literals in JS; `a + '건'` concatenation; Python f-strings,
    `+` concatenation, `.format()` and `%` formatting. Variables become {0}, {1}…
  - strings that carry HTML (innerHTML templates) are split into their text nodes and their
    translated attributes (placeholder, title, aria-label, alt, label, data-tooltip), line by line
Left out: comments and docstrings, console / logger / print calls, import paths, object keys, and
what SKIP_RULES below names (prompts and tool descriptions for agents, log lines, CLI output).
"""
import argparse
import ast
import fnmatch
import glob
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent      # the repository (robo-architect-lite)
DESKTOP = ROOT / 'desktop'
NODE_MODULES = ROOT / 'frontend/node_modules'
OUT_STRINGS = DESKTOP / 'i18n/strings.json'
OUT_MISSING = DESKTOP / 'i18n/missing.txt'
DICT = DESKTOP / 'resources/i18n/ko-en.json'

HANGUL = re.compile(r'[가-힣]')
PH = '\ue000'  # a variable part, before numbering

AN = 'robo-analyzer/robo-data-frontend/'
# (group, globs, excluded globs); the analyzer group is filled from its import closure (analyzer_files)
GROUPS = [
    ('frontend', ['frontend/src/**/*.vue', 'frontend/src/**/*.js', 'frontend/src/**/*.ts'],
     ['frontend/src/**/__tests__/**', 'frontend/src/**/*.spec.*', 'frontend/src/**/*.test.*']),
    ('analyzer', [], []),
    ('shell', ['desktop/resources/shell/*.js', 'desktop/resources/shell/*.html'], []),
    ('main', ['desktop/src/main/**/*.ts'], []),
    ('backend', ['api/features/**/*.py', 'api/platform/*.py'], ['api/**/tests/**', 'api/**/test_*.py']),
]

# ── backend: only messages the UI shows ──
# A backend string is kept when it is the value of one of these keys / keyword arguments, an
# exception's message (HTTPException detail …), or one of the BACKEND_ALL files below; and it is
# never a long prompt (BACKEND_MAX_LEN).
BACKEND_UI_KEYS = {'message', 'detail', 'label', 'title', 'question', 'rationale', 'reason', 'hint',
                   'error', 'warning', 'note', 'text', 'description', 'summary', 'placeholder', 'msg',
                   'status_message', 'statusMessage', 'phase_label', 'phaseLabel', 'step_label',
                   'options', 'recommended', 'display', 'displayName', 'name_ko', 'caption', 'tooltip'}
BACKEND_ALL = ['api/features/constitution/services/constitution_interview.py']
BACKEND_MAX_LEN = 240
BACKEND_PROMPTISH = re.compile(r'(반환하세요|출력하세요|JSON ?(으로|형식)|당신은|You are|응답 형식|스키마|규칙:|'
                               r'다음 (형식|규칙)|```|\{\{|^\s*-\s|^#+\s)')

# Strings that never reach a screen. Each rule names a file glob and any of:
#   fn    enclosing function (any level), glob     var   assigned variable / constant, glob
#   key   dict / object key the string is the value of, glob
#   call  function or method the string is an argument of, glob
#   text  regex on the extracted text                lines "a-b" line range (last resort)
#   all   True: the whole file
SKIP_RULES = [
    # ── anywhere ──
    {'file': '*', 'call': ['re.*', 'RegExp', '*.executescript', '*.execute', '*.run', 'session.run', 'tx.run'],
     'why': 'regex / SQL / Cypher'},
    {'file': '*', 'text': r'^(오늘 \{0\}|\{0\}월 \{1\}일|\{0\}년 \{1\}월 \{2\}일)$', 'why': 'date format (translate.js handles dates)'},
    {'file': '*', 'var': ['*PROMPT*', '*prompt*', '*_SYSTEM*', '*system_msg*', '*INSTRUCTION*', '*instruction*'],
     'why': 'LLM prompt'},
    {'file': '*', 'fn': ['*prompt*', '*Prompt*', '*_compose_*', '_build_user_*', '_build_system_*'], 'why': 'LLM prompt'},
    {'file': '*', 'call': ['SystemMessage', 'HumanMessage', 'AIMessage', '*.invoke', '*.ainvoke', 'ChatPromptTemplate.*'],
     'why': 'LLM prompt'},
    # ── frontend: prompts sent to Claude Code / the agents ──
    {'file': 'frontend/src/**', 'var': ['*Prompt', '*prompt', 'cmd', 'command', 'injected*'], 'why': 'agent prompt'},
    # ── backend files that only talk to agents / skills ──
    {'file': 'api/features/ingestion/**', 'fn': ['*_llm*', '*agent*'], 'why': 'LLM pipeline'},
    {'file': 'api/platform/skill_runner.py', 'all': True, 'why': 'skill runner (prompts)'},
    {'file': 'api/platform/global_skills.py', 'all': True, 'why': 'skill installer'},
    {'file': 'api/platform/observability/**', 'all': True, 'why': 'logging'},
    {'file': 'api/features/llm_bridge/**', 'all': True, 'why': 'LLM bridge'},
    {'file': 'api/features/**/*mcp*.py', 'all': True, 'why': 'MCP server for agents'},
    {'file': 'api/**', 'call': ['Field', '*.Field', 'Query', 'File', 'Form', 'Body', 'Path'],
     'why': 'field description for the LLM / OpenAPI'},
    {'file': 'api/features/requirements/chat_edit/chat_edit_agent.py', 'var': '_FIELD_GUIDE', 'why': 'LLM field guide'},
    # ── frontend / analyzer: not text on screen ──
    {'file': 'frontend/src/features/exportDocument/ui/ExportDocumentDialog.vue', 'text': r'^<!DOCTYPE', 'why': 'print-window template'},
    {'file': 'frontend/src/features/exportDocument/ui/exporters/captureExporter.js', 'text': r'^맑은 고딕$', 'why': 'font name'},
    {'file': AN + 'src/features/code-analysis/areaGraph.ts', 'text': r'^__기타__$', 'why': 'internal key'},
    {'file': AN + 'src/features/code-analysis/components/graph/GraphTab.vue', 'text': r'^에러$', 'why': 'string test, not shown'},
    {'file': AN + 'src/workflows/schema-modeling/composables/useSchemaCanvasTableIntake.ts', 'text': r'^\[SchemaCanvas\]', 'why': 'log line'},
    # ── Electron main ──
    {'file': 'desktop/src/main/index.ts', 'text': r'^한국어$', 'why': 'the language menu names each language in its own language'},
]

# Attributes in Vue templates whose static values are not text (the rest, including component
# props such as title / label / description, are rendered somewhere).
NON_TEXT_ATTRS = {'class', 'style', 'id', 'key', 'ref', 'name', 'type', 'for', 'href', 'src', 'role',
                  'data-testid', 'data-test', 'viewBox', 'd', 'fill', 'stroke', 'lang', 'is', 'slot',
                  'xmlns', 'target', 'rel', 'autocomplete', 'spellcheck', 'accept', 'pattern'}
TRANSLATED_HTML_ATTRS = ('title', 'placeholder', 'aria-label', 'alt', 'label', 'data-tooltip')
LOG_CALLS = re.compile(r'^(console\.\w+|log|dlog|logger\.\w+|logging\.\w+|log\.\w+|LOG\.\w+|_log\w*|print|'
                       r'warnings\.warn|(self|cls)\._?log\w*(\.\w+)?|.*\.(logger|_logger|log|_log)\.\w+|\w*Logger\.\w+)$')


# ─────────────────────────────── JS / Vue / TS (Node helper) ───────────────────────────────
NODE_HELPER = r"""
'use strict'
const fs = require('fs')
const path = require('path')
const [NM, listFile] = process.argv.slice(2)
const babel = require(path.join(NM, '@babel/parser'))
const sfc = require(path.join(NM, '@vue/compiler-sfc'))
const HANGUL = /[가-힣]/
const PH = '\uE000'
const RAW_TAGS = new Set(['pre', 'code', 'textarea', 'script', 'style'])
const NON_TEXT_ATTRS = new Set(JSON.parse(process.env.NON_TEXT_ATTRS || '[]'))
const out = []
const errors = []

function plugins(lang) {
  const p = ['decorators-legacy', 'classProperties', 'optionalChaining', 'importMeta', 'topLevelAwait']
  if (lang === 'ts') p.push('typescript')
  return p
}

// ── context of a node: enclosing function names, variable, object key, call ──
function keyName(k) {
  if (!k) return null
  if (k.type === 'Identifier') return k.name
  if (k.type === 'StringLiteral') return k.value
  if (k.type === 'PrivateName') return k.id.name
  return null
}
function calleeName(c) {
  if (!c) return null
  if (c.type === 'Identifier') return c.name
  if (c.type === 'MemberExpression' || c.type === 'OptionalMemberExpression') {
    const o = calleeName(c.object) || (c.object.type === 'ThisExpression' ? 'this' : '?')
    const p = c.computed ? '?' : keyName(c.property)
    return o + '.' + p
  }
  if (c.type === 'CallExpression') return calleeName(c.callee) + '()'
  return null
}
function context(anc, node) {
  const fns = []
  let v = null, key = null, call = null
  let child = node
  for (let i = anc.length - 1; i >= 0; i--) {
    const a = anc[i]
    const t = a.type
    if (t === 'FunctionDeclaration' && a.id) fns.unshift(a.id.name)
    else if (t === 'ObjectMethod' || t === 'ClassMethod' || t === 'ClassPrivateMethod') fns.unshift(keyName(a.key) || '?')
    else if (t === 'FunctionExpression' || t === 'ArrowFunctionExpression') {
      const p = anc[i - 1]
      let n = a.id ? a.id.name : null
      if (!n && p) {
        if (p.type === 'VariableDeclarator') n = keyName(p.id)
        else if (p.type === 'ObjectProperty' || p.type === 'ClassProperty') n = keyName(p.key)
        else if (p.type === 'AssignmentExpression') n = calleeName(p.left)
      }
      if (n) fns.unshift(n)
    }
    if (v === null && t === 'VariableDeclarator') v = keyName(a.id)
    if (v === null && t === 'AssignmentExpression') v = calleeName(a.left)
    if (v === null && (t === 'ClassProperty')) v = keyName(a.key)
    if (key === null && t === 'ObjectProperty' && a.value === child) key = keyName(a.key)
    if (call === null && (t === 'CallExpression' || t === 'NewExpression' || t === 'OptionalCallExpression') && a.callee !== child) call = calleeName(a.callee)
    child = a
  }
  return { fns, var: v, key, call }
}
function inLogCall(anc) {
  for (let i = anc.length - 1; i >= 0; i--) {
    const a = anc[i]
    if (a.type === 'CallExpression' || a.type === 'OptionalCallExpression') {
      const n = calleeName(a.callee) || ''
      if (/^console\./.test(n)) return true
    }
  }
  return false
}

function emit(file, line, s, mode, ctx) {
  if (!HANGUL.test(s)) return
  out.push({ file, line, s, mode, ctx })
}

// ── JS ──
function children(node) {
  const r = []
  for (const k of Object.keys(node)) {
    if (k === 'loc' || k === 'start' || k === 'end' || k === 'extra' || k === 'leadingComments' || k === 'trailingComments' || k === 'innerComments' || k === 'range') continue
    const v = node[k]
    if (Array.isArray(v)) { for (const x of v) if (x && typeof x.type === 'string') r.push(x) }
    else if (v && typeof v.type === 'string') r.push(v)
  }
  return r
}
function flatPlus(n) {
  if (n.type === 'BinaryExpression' && n.operator === '+') return [...flatPlus(n.left), ...flatPlus(n.right)]
  return [n]
}
function hasKoreanLiteral(n) {
  if (n.type === 'StringLiteral') return HANGUL.test(n.value)
  if (n.type === 'TemplateLiteral') return n.quasis.some((q) => HANGUL.test(q.value.cooked ?? q.value.raw))
  return false
}
function scanJs(code, file, lineOffset, lang, asExpr) {
  let ast
  try {
    if (asExpr) {
      try { ast = babel.parseExpression(code, { plugins: plugins(lang), errorRecovery: true }) }
      catch { ast = babel.parse(code, { sourceType: 'module', plugins: plugins(lang), errorRecovery: true, allowReturnOutsideFunction: true, allowAwaitOutsideFunction: true }) }
    } else {
      ast = babel.parse(code, { sourceType: 'unambiguous', plugins: plugins(lang), errorRecovery: true, allowReturnOutsideFunction: true, allowAwaitOutsideFunction: true, allowImportExportEverywhere: true })
    }
  } catch (e) { errors.push(`${file}:${lineOffset + 1}: ${e.message}`); return }
  const L = (n) => (n.loc ? n.loc.start.line : 1) + lineOffset
  const anc = []
  const skip = (node) => {
    const p = anc[anc.length - 1]
    if (!p) return false
    if ((p.type === 'ObjectProperty' || p.type === 'ClassProperty' || p.type === 'ObjectMethod' || p.type === 'ClassMethod') && p.key === node && !p.computed) return true
    if (p.type === 'ImportDeclaration' || p.type === 'ExportAllDeclaration' || p.type === 'ExportNamedDeclaration' || p.type === 'ImportExpression') return true
    if (p.type === 'CallExpression' && p.callee && p.callee.type === 'Identifier' && p.callee.name === 'require') return true
    if (p.type === 'TSLiteralType' || p.type === 'Directive' || p.type === 'DirectiveLiteral') return true
    return inLogCall(anc)
  }
  // a ${...} part: a string literal is its text, anything else a variable part
  function part(e) {
    if (e.type === 'StringLiteral') return e.value
    visit(e)
    return PH
  }
  function visit(node) {
    if (!node || typeof node.type !== 'string') return
    if (node.type === 'BinaryExpression' && node.operator === '+') {
      const parent = anc[anc.length - 1]
      const top = !(parent && parent.type === 'BinaryExpression' && parent.operator === '+')
      const ops = flatPlus(node)
      if (top && ops.some(hasKoreanLiteral)) {
        let s = ''
        anc.push(node)
        for (const o of ops) {
          if (o.type === 'StringLiteral') s += o.value
          else if (o.type === 'TemplateLiteral') {
            o.quasis.forEach((q, i) => { s += q.value.cooked ?? q.value.raw; if (i < o.expressions.length) s += part(o.expressions[i]) })
          } else { s += PH; visit(o) }
        }
        anc.pop()
        if (!skip(node)) emit(file, L(node), s, 'js', context(anc, node))
        return
      }
    }
    if (node.type === 'TemplateLiteral') {
      const parent = anc[anc.length - 1]
      if (!(parent && parent.type === 'TaggedTemplateExpression')) {
        let s = ''
        anc.push(node)
        node.quasis.forEach((q, i) => { s += q.value.cooked ?? q.value.raw; if (i < node.expressions.length) s += part(node.expressions[i]) })
        anc.pop()
        if (HANGUL.test(s.replace(/\uE000/g, '')) && !skip(node)) emit(file, L(node), s, 'js', context(anc, node))
        return
      }
    }
    if (node.type === 'StringLiteral') {
      if (HANGUL.test(node.value) && !skip(node)) emit(file, L(node), node.value, 'js', context(anc, node))
      return
    }
    if (node.type === 'RegExpLiteral') return
    anc.push(node)
    for (const c of children(node)) visit(c)
    anc.pop()
  }
  visit(ast.program || ast)
}

// ── Vue SFC ──
function scanVue(src, file) {
  const { descriptor, errors: errs } = sfc.parse(src, { filename: file })
  for (const e of errs || []) errors.push(`${file}: ${e.message || e}`)
  for (const blk of [descriptor.script, descriptor.scriptSetup]) {
    if (blk) scanJs(blk.content, file, blk.loc.start.line - 1, blk.lang === 'ts' ? 'ts' : 'js', false)
  }
  if (!descriptor.template || !descriptor.template.ast) return
  const lang = (descriptor.scriptSetup || descriptor.script || {}).lang === 'ts' ? 'ts' : 'js'
  const expr = (code, line, attr) => { if (HANGUL.test(code)) scanJs(code, file, line - 1, lang, true) }
  function el(node, raw) {
    for (const p of node.props || []) {
      if (p.type === 6) {
        if (p.value && HANGUL.test(p.value.content) && !NON_TEXT_ATTRS.has(p.name)) emit(file, p.loc.start.line, p.value.content, 'tpl', { attr: p.name, tag: node.tag })
      } else if (p.type === 7) {
        if (p.exp && HANGUL.test(p.exp.content)) {
          let code = p.exp.content
          if (p.name === 'for') code = code.replace(/^[\s\S]*?\s(?:in|of)\s/, '')
          if (p.name === 'slot') continue
          expr(code, p.exp.loc.start.line, p.rawName)
        }
      }
    }
    const isRaw = raw || RAW_TAGS.has(node.tag)
    let run = []
    const flush = () => {
      if (!run.length) return
      let s = ''
      for (const c of run) {
        if (c.type === 2) s += c.content
        else { s += PH; expr(c.content.content || '', c.content.loc ? c.content.loc.start.line : c.loc.start.line) }
      }
      if (!isRaw) emit(file, run[0].loc.start.line, s, 'tpl', { tag: node.tag })
      run = []
    }
    for (const c of node.children || []) {
      if (c.type === 2 || c.type === 5) run.push(c)
      else if (c.type === 3) continue
      else { flush(); if (c.type === 1) el(c, isRaw) }
    }
    flush()
  }
  el(descriptor.template.ast, false)
}

// ── static HTML ──
function scanHtml(src, file) {
  let blanked = src.replace(/<(script|style)\b([^>]*)>([\s\S]*?)<\/\1>/gi, (m, tag, attrs, body, off) => {
    if (tag.toLowerCase() === 'script' && !/\bsrc=/.test(attrs)) {
      const line = src.slice(0, off).split('\n').length + (m.slice(0, m.indexOf('>') + 1).split('\n').length - 1)
      scanJs(body, file, line - 1, 'js', false)
    }
    return m.replace(/[^\n]/g, ' ')
  })
  blanked = blanked.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '))
  emit(file, 1, blanked, 'html', { tag: 'html' })
}

for (const f of JSON.parse(fs.readFileSync(listFile, 'utf8'))) {
  const src = fs.readFileSync(f.abs, 'utf8')
  if (!HANGUL.test(src)) continue
  try {
    if (f.abs.endsWith('.vue')) scanVue(src, f.rel)
    else if (f.abs.endsWith('.html')) scanHtml(src, f.rel)
    else scanJs(src, f.rel, 0, f.abs.endsWith('.ts') ? 'ts' : 'js', false)
  } catch (e) { errors.push(`${f.rel}: ${e.stack || e}`) }
}
process.stdout.write(JSON.stringify({ out, errors }))
"""


def scan_js_files(files):
    if not (NODE_MODULES / '@babel/parser').exists() or not (NODE_MODULES / '@vue/compiler-sfc').exists():
        sys.exit(f'{NODE_MODULES} has no @babel/parser / @vue/compiler-sfc — run npm install in frontend first')
    with tempfile.TemporaryDirectory() as tmp:
        helper = Path(tmp) / 'scan.cjs'
        helper.write_text(NODE_HELPER, encoding='utf-8')
        lst = Path(tmp) / 'files.json'
        lst.write_text(json.dumps([{'abs': str(ROOT / f), 'rel': f} for f in files]), encoding='utf-8')
        env = dict(os.environ, NON_TEXT_ATTRS=json.dumps(sorted(NON_TEXT_ATTRS)))
        r = subprocess.run(['node', str(helper), str(NODE_MODULES), str(lst)], capture_output=True, text=True, env=env)
        if r.returncode != 0:
            sys.exit('node helper failed:\n' + r.stderr)
        data = json.loads(r.stdout)
    for e in data['errors']:
        print('warning:', e, file=sys.stderr)
    return data['out']


# ─────────────────────────────── analyzer: what the Legacy tab can reach ───────────────────────────────
DEPS_HELPER = r"""
'use strict'
const fs = require('fs')
const path = require('path')
const [NM, listFile] = process.argv.slice(2)
const babel = require(path.join(NM, '@babel/parser'))
const sfc = require(path.join(NM, '@vue/compiler-sfc'))
const out = {}
function scan(code, lang, acc) {
  let ast
  try {
    ast = babel.parse(code, { sourceType: 'module', errorRecovery: true,
      plugins: ['decorators-legacy', 'classProperties', 'optionalChaining', 'importMeta', 'topLevelAwait', ...(lang === 'ts' ? ['typescript'] : [])] })
  } catch (e) { return }
  const visit = (n) => {
    if (!n || typeof n.type !== 'string') return
    if ((n.type === 'ImportDeclaration' || n.type === 'ExportAllDeclaration' || n.type === 'ExportNamedDeclaration') && n.source)
      acc.push({ spec: n.source.value, dynamic: false, line: n.loc.start.line })
    if (n.type === 'CallExpression' && n.callee && n.callee.type === 'Import' && n.arguments[0] && n.arguments[0].type === 'StringLiteral')
      acc.push({ spec: n.arguments[0].value, dynamic: true, line: n.loc.start.line })
    if (n.type === 'ImportExpression' && n.source && n.source.type === 'StringLiteral')
      acc.push({ spec: n.source.value, dynamic: true, line: n.loc.start.line })
    for (const k of Object.keys(n)) {
      if (k === 'loc' || k === 'start' || k === 'end' || k === 'extra') continue
      const v = n[k]
      if (Array.isArray(v)) v.forEach(visit)
      else if (v && typeof v.type === 'string') visit(v)
    }
  }
  visit(ast.program)
}
for (const f of JSON.parse(fs.readFileSync(listFile, 'utf8'))) {
  const src = fs.readFileSync(f, 'utf8')
  const acc = []
  if (f.endsWith('.vue')) {
    const { descriptor } = sfc.parse(src, { filename: f })
    for (const b of [descriptor.script, descriptor.scriptSetup]) if (b) scan(b.content, b.lang === 'ts' ? 'ts' : 'js', acc)
  } else scan(src, f.endsWith('.ts') ? 'ts' : 'js', acc)
  out[f] = acc
}
process.stdout.write(JSON.stringify(out))
"""
AN_ENTRY = AN + 'src/bootstrap.ts'
AN_FEATURES = AN + 'src/app/config/features.ts'


def _embedded_imports():
    """The import() targets of the features Lite embeds (embeddable: true in features.ts)."""
    src = (ROOT / AN_FEATURES).read_text(encoding='utf-8')
    body = src[src.index('export const FEATURES'):]
    keep = set()
    for chunk in re.split(r'\{\s*id:\s*', body)[1:]:
        if re.search(r'embeddable:\s*true', chunk):
            keep.update(re.findall(r"import\('([^']+)'\)", chunk))
    return keep


def _resolve(spec, frm):
    if spec.startswith('@/'):
        base = ROOT / AN / 'src' / spec[2:]
    elif spec.startswith('.'):
        base = (ROOT / frm).parent / spec
    else:
        return None  # a package
    base = Path(os.path.normpath(base))
    for cand in [base, *(base.with_name(base.name + e) for e in ('.ts', '.js', '.vue')),
                 base / 'index.ts', base / 'index.js']:
        if cand.is_file() and cand.suffix in ('.ts', '.js', '.vue'):
            return os.path.relpath(cand, ROOT)
    return None


def analyzer_files():
    """The analyzer sources Lite's Legacy tab can load: the import closure of the remote entry,
    following import() everywhere except in features.ts, where only the embedded features count."""
    if not (ROOT / AN_ENTRY).exists():
        return []
    embedded = _embedded_imports()
    seen, todo = set(), [AN_ENTRY]
    with tempfile.TemporaryDirectory() as tmp:
        helper = Path(tmp) / 'deps.cjs'
        helper.write_text(DEPS_HELPER, encoding='utf-8')
        while todo:
            batch = [f for f in dict.fromkeys(todo) if f not in seen]
            todo = []
            if not batch:
                break
            seen.update(batch)
            lst = Path(tmp) / 'files.json'
            lst.write_text(json.dumps([str(ROOT / f) for f in batch]), encoding='utf-8')
            r = subprocess.run(['node', str(helper), str(NODE_MODULES), str(lst)], capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit('deps helper failed:\n' + r.stderr)
            for absf, deps in json.loads(r.stdout).items():
                rel = os.path.relpath(absf, ROOT)
                for d in deps:
                    if rel == AN_FEATURES and d['dynamic'] and d['spec'] not in embedded:
                        continue
                    t = _resolve(d['spec'], rel)
                    if t and t not in seen:
                        todo.append(t)
    return sorted(f for f in seen if not f.endswith('.d.ts'))


def backend_keep(c, text):
    """A backend string the UI shows (see BACKEND_UI_KEYS)."""
    if any(fnmatch.fnmatch(c['file'], g) for g in BACKEND_ALL):
        return len(text) <= BACKEND_MAX_LEN * 2 and not BACKEND_PROMPTISH.search(text)
    if len(text) > BACKEND_MAX_LEN or BACKEND_PROMPTISH.search(text):
        return False
    ctx = c.get('ctx') or {}
    if ctx.get('key') in BACKEND_UI_KEYS:
        return True
    call = ctx.get('call') or ''
    if re.search(r'(Exception|Error)$', call.split('.')[-1]):
        return True
    return False


# ─────────────────────────────── Python (ast) ───────────────────────────────
FORMAT_FIELD = re.compile(r'\{\{|\}\}|\{[^{}]*\}')
PERCENT_FIELD = re.compile(r'%%|%(\([^)]*\))?[-#0 +]*(\*|\d+)?(\.(\*|\d+))?[sdifrxXeEgGc]')


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return (_dotted(node.value) or '?') + '.' + node.attr
    if isinstance(node, ast.Call):
        return (_dotted(node.func) or '?') + '()'
    return None


def scan_py_file(rel):
    src = (ROOT / rel).read_text(encoding='utf-8')
    if not HANGUL.search(src):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f'warning: {rel}:{e.lineno}: {e.msg}', file=sys.stderr)
        return []
    parent = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    out = []
    consumed = set()

    def is_str(n):
        return isinstance(n, ast.Constant) and isinstance(n.value, str)

    def ctx_of(node):
        fns, var, key, call, kw = [], None, None, None, None
        child, a = node, parent.get(node)
        while a is not None:
            if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                fns.insert(0, a.name)
            elif isinstance(a, ast.Lambda):
                pass
            if var is None and isinstance(a, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                tgt = a.targets[0] if isinstance(a, ast.Assign) else a.target
                sl = getattr(tgt, 'slice', None)
                if isinstance(sl, getattr(ast, 'Index', ())):
                    sl = sl.value
                if isinstance(tgt, ast.Subscript) and is_str(sl):
                    var = (_dotted(tgt.value) or '?') + '[' + sl.value + ']'
                else:
                    var = _dotted(tgt)
            if key is None and isinstance(a, ast.Dict):
                for k, v in zip(a.keys, a.values):
                    if v is child and k is not None and is_str(k):
                        key = k.value
            if kw is None and isinstance(a, ast.keyword) and a.arg:
                kw = a.arg
            if call is None and isinstance(a, ast.Call) and a.func is not child:
                call = _dotted(a.func)
            child, a = a, parent.get(a)
        if key is None and kw is not None:
            key = kw
        return {'fns': fns, 'var': var, 'key': key, 'call': call}

    def in_log(node):
        a = parent.get(node)
        child = node
        while a is not None:
            if isinstance(a, ast.Call) and a.func is not child:
                name = _dotted(a.func) or ''
                if LOG_CALLS.match(name):
                    return True
            child, a = a, parent.get(a)
        return False

    def is_docstring(node):
        p = parent.get(node)
        return isinstance(p, ast.Expr)  # a bare string statement: docstring or comment-like

    def joined(n):
        s = ''
        for v in n.values:
            if is_str(v):
                s += v.value
                consumed.add(v)
            else:
                s += PH
        return s

    def flat_add(n):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            return flat_add(n.left) + flat_add(n.right)
        return [n]

    def emit(node, s):
        if HANGUL.search(s.replace(PH, '')) and not in_log(node) and not is_docstring(node):
            out.append({'file': rel, 'line': node.lineno, 's': s, 'mode': 'py', 'ctx': ctx_of(node)})

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            p = parent.get(node)
            if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Add):
                continue
            ops = flat_add(node)
            if not any((is_str(o) and HANGUL.search(o.value)) or isinstance(o, ast.JoinedStr) for o in ops):
                continue
            s = ''
            for o in ops:
                if is_str(o):
                    s += o.value
                    consumed.add(o)
                elif isinstance(o, ast.JoinedStr):
                    s += joined(o)
                    consumed.add(o)
                else:
                    s += PH
            emit(node, s)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and is_str(node.left) and HANGUL.search(node.left.value):
            consumed.add(node.left)
            emit(node, PERCENT_FIELD.sub(lambda m: '%' if m.group(0) == '%%' else PH, node.left.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'format' \
                and is_str(node.func.value) and HANGUL.search(node.func.value.value):
            consumed.add(node.func.value)
            emit(node, FORMAT_FIELD.sub(lambda m: m.group(0)[0] if m.group(0) in ('{{', '}}') else PH, node.func.value.value))

    for node in ast.walk(tree):
        if node in consumed:
            continue
        if isinstance(node, ast.JoinedStr):
            p = parent.get(node)
            if isinstance(p, ast.JoinedStr):  # nested format spec
                continue
            emit(node, joined(node))
        elif is_str(node) and HANGUL.search(node.value):
            p = parent.get(node)
            if isinstance(p, ast.JoinedStr) or isinstance(p, ast.FormattedValue):
                continue
            emit(node, node.value)
    return out


# ─────────────────────────────── candidates → entries ───────────────────────────────
TAG = re.compile(r'<!--[\s\S]*?-->|</?[a-zA-Z][\w:-]*(?:\s[^<>]*)?/?>')
TAG_ATTR = re.compile(r'\s(' + '|'.join(TRANSLATED_HTML_ATTRS) + r')\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
LOOKS_HTML = re.compile(r'</?(?:a|b|i|u|s|p|br|hr|em|strong|small|span|div|li|ul|ol|h[1-6]|code|kbd|label|button|svg|img|'
                        r'input|select|option|table|thead|tbody|tr|td|th|section|header|footer|nav|main|aside|details|'
                        r'summary|mark|sup|sub|time|abbr|pre|textarea|form|fieldset|legend|small|dl|dt|dd|iframe)\b[^<>]*>', re.I)


def split_html(s):
    """Text chunks of an HTML string with their offsets: the text between tags and translated attributes."""
    chunks, last = [], 0
    for m in TAG.finditer(s):
        chunks.append((last, s[last:m.start()]))
        for a in TAG_ATTR.finditer(m.group(0)):
            chunks.append((m.start(), a.group(2) if a.group(2) is not None else a.group(3)))
        last = m.end()
    chunks.append((last, s[last:]))
    return chunks


def finalize(c):
    """One candidate → [(kind, text, line)] as the translator will see it (trimmed, per text node)."""
    s, mode, line = c['s'], c['mode'], c['line']
    pieces = []
    if mode == 'html' or (mode in ('js', 'py') and LOOKS_HTML.search(s)):
        for off, chunk in split_html(s):
            ln = line + s.count('\n', 0, off)
            chunk = html.unescape(chunk)
            for i, part in enumerate(chunk.split('\n')):
                pieces.append((part, ln + i))
    else:
        pieces.append((s, line))
    res = []
    for text, ln in pieces:
        text = re.sub(PH + '{2,}', PH, text)
        text = text.strip()
        if not HANGUL.search(text.replace(PH, '')):
            continue
        # leading / trailing variable parts glued to nothing but spaces are kept — they are on screen
        if PH in text:
            n = iter(range(1000))
            text = re.sub(PH, lambda m: '{%d}' % next(n), text)
            res.append(('pattern', text, ln))
        else:
            res.append(('exact', text, ln))
    return res


# ─────────────────────────────── skip rules ───────────────────────────────
def skip_reason(c, kind, text, line):
    ctx = c.get('ctx') or {}
    if c['mode'] == 'js' and ctx.get('call') and LOG_CALLS.match(ctx['call']):
        return 'log line'
    for r in SKIP_RULES:
        if not any(fnmatch.fnmatch(c['file'], g) for g in (r['file'] if isinstance(r['file'], list) else [r['file']])):
            continue
        conds = []
        if r.get('all'):
            conds.append(True)
        if 'fn' in r:
            pats = r['fn'] if isinstance(r['fn'], list) else [r['fn']]
            conds.append(any(fnmatch.fnmatchcase(f, p) for f in ctx.get('fns', []) for p in pats))
        if 'var' in r:
            pats = r['var'] if isinstance(r['var'], list) else [r['var']]
            conds.append(ctx.get('var') is not None and any(fnmatch.fnmatchcase(ctx['var'], p) for p in pats))
        if 'key' in r:
            pats = r['key'] if isinstance(r['key'], list) else [r['key']]
            conds.append(ctx.get('key') is not None and any(fnmatch.fnmatchcase(ctx['key'], p) for p in pats))
        if 'call' in r:
            pats = r['call'] if isinstance(r['call'], list) else [r['call']]
            conds.append(ctx.get('call') is not None and any(fnmatch.fnmatchcase(ctx['call'], p) for p in pats))
        if 'text' in r:
            conds.append(re.search(r['text'], text) is not None)
        if 'lines' in r:
            a, b = (int(x) for x in r['lines'].split('-'))
            conds.append(a <= c['line'] <= b)
        if conds and all(conds):
            return r.get('why', 'skip rule')
    return None


# ─────────────────────────────── dictionary check (translate.js core, in Python) ───────────────────────────────
class Translator:
    def __init__(self, d):
        self.exact = d.get('exact', {})
        self.pats = []
        for ko, en in d.get('patterns', []):
            parts = re.split(r'\{(\d+)\}', ko)
            rx, order = '^', []
            for i, p in enumerate(parts):
                if i % 2:
                    rx += r'([\s\S]+?)'
                    order.append(int(p))
                else:
                    rx += re.escape(p)
            self.pats.append((re.compile(rx + '$'), order, en, len(re.sub(r'\{\d+\}', '', ko)), ko))
        self.pats.sort(key=lambda p: -p[3])  # stable, like Array.prototype.sort in V8
        self.cache = {}

    def core(self, s):
        if s in self.exact:
            return self.exact[s]
        for rx, order, en, _, _ in self.pats:
            m = rx.match(s)
            if not m:
                continue
            vals = {n: self.tr(m.group(i + 1)) for i, n in enumerate(order)}
            return re.sub(r'\{(\d+)\}', lambda mm: vals.get(int(mm.group(1)), ''), en)
        return None

    def tr(self, s):
        if not HANGUL.search(s):
            return s
        if s in self.cache:
            return self.cache[s]
        m = re.match(r'^(\s*)([\s\S]*?)(\s*)$', s)
        lead, body, tail = m.groups()
        out = self.core(body)
        if out is None and '\n' in body:
            lines = [self.tr(x) for x in body.split('\n')]
            if any(a != b for a, b in zip(lines, body.split('\n'))):
                out = '\n'.join(lines)
        if out is None:
            out = body
        out = lead + out + tail
        self.cache[s] = out
        return out


def covered(t, kind, text, pattern_keys):
    if kind == 'exact':
        return text in t.exact or not HANGUL.search(t.tr(text))
    if text in pattern_keys:
        return True
    probe = re.sub(r'\{(\d+)\}', lambda m: 'x%sx' % m.group(1), text)  # the variable parts as neutral text
    return not HANGUL.search(t.tr(probe))


# ─────────────────────────────── main ───────────────────────────────
def files_of(globs, excludes):
    seen = []
    for g in globs:
        for f in sorted(glob.glob(str(ROOT / g), recursive=True)):
            rel = os.path.relpath(f, ROOT)
            if os.path.isfile(f) and rel not in seen and not any(fnmatch.fnmatch(rel, x) for x in excludes):
                seen.append(rel)
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='exit 1 when missing.txt is not empty')
    ap.add_argument('--json-missing', metavar='FILE', help='also write the missing entries as JSON (to translate)')
    args = ap.parse_args()

    group_of, js_files, py_files = {}, [], []
    for group, globs, excludes in GROUPS:
        for f in (analyzer_files() if group == 'analyzer' else files_of(globs, excludes)):
            group_of.setdefault(f, group)
            (py_files if f.endswith('.py') else js_files).append(f)

    cands = scan_js_files(js_files)
    for f in py_files:
        cands.extend(scan_py_file(f))

    entries, skipped = {}, {}
    for c in cands:
        group = group_of[c['file']]
        for kind, text, line in finalize(c):
            src = f"{c['file']}:{line}"
            why = skip_reason(c, kind, text, line)
            if not why and group == 'backend' and not backend_keep(c, text):
                why = 'backend: not a UI message'
            bucket = skipped if why else entries
            e = bucket.setdefault((kind, text), {'text': text, 'kind': kind, 'groups': [], 'sources': []})
            if group not in e['groups']:
                e['groups'].append(group)
            if src not in e['sources']:
                e['sources'].append(src)
            if why:
                e['why'] = why
    # a string kept anywhere is not "skipped"
    for k in list(skipped):
        if k in entries:
            del skipped[k]

    order = {g[0]: i for i, g in enumerate(GROUPS)}

    def sort_key(e):
        f, _, ln = e['sources'][0].rpartition(':')
        return (order[e['groups'][0]], f, int(ln), e['text'])

    strings = sorted(entries.values(), key=sort_key)
    skipped_list = sorted(skipped.values(), key=sort_key)

    prev = set()
    if OUT_STRINGS.exists():
        try:
            prev = {(e['kind'], e['text']) for e in json.loads(OUT_STRINGS.read_text(encoding='utf-8'))['strings']}
        except Exception:
            pass

    by_group = {g[0]: {'exact': 0, 'pattern': 0} for g in GROUPS}
    for e in strings:
        by_group[e['groups'][0]][e['kind']] += 1
    OUT_STRINGS.parent.mkdir(parents=True, exist_ok=True)
    OUT_STRINGS.write_text(json.dumps({
        'about': 'Korean UI text that can reach a screen. Generated by scripts/i18n-extract.py — do not edit.',
        'counts': {'exact': sum(1 for e in strings if e['kind'] == 'exact'),
                   'pattern': sum(1 for e in strings if e['kind'] == 'pattern'),
                   'skipped': len(skipped_list), 'by_group (first group)': by_group},
        'strings': strings,
        'skipped': skipped_list,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    d = {'exact': {}, 'patterns': []}
    if DICT.exists():
        d = json.loads(DICT.read_text(encoding='utf-8'))
    t = Translator(d)
    pattern_keys = {ko for ko, _ in d.get('patterns', [])}
    missing = [e for e in strings if not covered(t, e['kind'], e['text'], pattern_keys)]
    used = {e['text'] for e in strings}
    unused = [k for k in d.get('exact', {}) if k not in used] + [ko for ko, _ in d.get('patterns', []) if ko not in used]

    lines = [f'# {len(missing)} extracted string(s) not translated by {DICT.relative_to(ROOT)}',
             f'# ({len(strings)} extracted: {sum(1 for e in strings if e["kind"] == "exact")} exact, '
             f'{sum(1 for e in strings if e["kind"] == "pattern")} patterns; {len(skipped_list)} skipped by rules; '
             f'{len(unused)} dictionary entries not extracted — runtime data, fragments or stale)',
             '# kind<TAB>text<TAB>first source   ([new] = not in the previous strings.json)', '']
    for e in missing:
        mark = '' if (e['kind'], e['text']) in prev or not prev else '[new] '
        lines.append(f"{mark}{e['kind']}\t{json.dumps(e['text'], ensure_ascii=False)[1:-1]}\t{e['sources'][0]}")
    OUT_MISSING.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if args.json_missing:
        Path(args.json_missing).write_text(json.dumps(
            [{'kind': e['kind'], 'ko': e['text'], 'src': e['sources'][0], 'group': e['groups'][0]} for e in missing],
            ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    print(f"{len(strings)} strings ({by_group}), {len(skipped_list)} skipped, {len(missing)} missing → "
          f"{OUT_STRINGS.relative_to(ROOT)}, {OUT_MISSING.relative_to(ROOT)}")
    if args.check and missing:
        sys.exit(1)


if __name__ == '__main__':
    main()
