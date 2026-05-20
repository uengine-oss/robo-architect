#!/usr/bin/env bun
/**
 * Build script: transpile plugin.ts → plugin.js with inlined ui.html.
 *
 * Avoids bun's commonJS/ESM wrappers that break Figma's sandbox.
 * Uses Bun.Transpiler for pure TS→JS conversion.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'fs'

// 1. Transpile plugin.ts (TS → JS, no module wrapping)
const tsCode = readFileSync(new URL('src/plugin.ts', import.meta.url), 'utf-8')
const transpiler = new Bun.Transpiler({ loader: 'ts', target: 'browser' })
let jsCode = transpiler.transformSync(tsCode)

// 2. Read ui.html and inline as __html__
const uiHtml = readFileSync(new URL('src/ui.html', import.meta.url), 'utf-8')
const htmlJsonStr = JSON.stringify(uiHtml)

// 3. Prepend __html__ variable
const finalJs = `var __html__ = ${htmlJsonStr};\n${jsCode}`

// 4. Write output
mkdirSync(new URL('dist', import.meta.url), { recursive: true })
writeFileSync(new URL('dist/plugin.js', import.meta.url), finalJs)

console.log(`Built dist/plugin.js (${(finalJs.length / 1024).toFixed(1)} KB) with inlined UI`)
