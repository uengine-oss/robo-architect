#!/usr/bin/env node
// TypeScript class-field extractor for /robo-sync (feature 029).
//
// MVP implementation: regex-based. Walks an `export class X { ... }`
// declaration and emits its top-level field declarations. This is
// deliberately not a full AST parse — it covers the common shape
// /robo-implement scaffolds (one aggregate per file, fields declared
// at the top, constructor below). The full AST version (using
// @typescript-eslint/typescript-estree) is a follow-on task; this
// stub is enough for the end-to-end /robo-sync round trip used in the
// manual.
//
// Output: a single JSON document on stdout of the shape
//   {
//     "kind": "Aggregate",                 // heuristic, see below
//     "name": "MemberAccount",
//     "fields": [ { "name": "...", "type": "..." }, ... ]
//   }
//
// `kind` is heuristic: "Aggregate" when the file path contains
// `/entities/` (Clean Architecture convention used by /robo-implement
// for `core` BCs). The caller (/robo-sync skill) is responsible for
// resolving each name to a real elementId via MCP get_bc_design.

import { readFileSync } from 'node:fs'

const [, , filePath] = process.argv
if (!filePath) {
    process.stderr.write('usage: node ts_extract.mjs <path-to-ts-file>\n')
    process.exit(2)
}

let src
try {
    src = readFileSync(filePath, 'utf-8')
} catch (e) {
    process.stderr.write(`ts_extract.mjs: cannot read ${filePath}: ${e.message}\n`)
    process.exit(2)
}

// 1. Find the first exported class declaration.
const classMatch = src.match(/export\s+class\s+(\w+)\s*\{/)
if (!classMatch) {
    process.stderr.write('ts_extract.mjs: no `export class ...` found\n')
    process.exit(0) // not an error; just nothing to emit
}
const className = classMatch[1]
const classBodyStart = classMatch.index + classMatch[0].length

// 2. Find the matching closing brace for the class body (balanced).
let depth = 1
let i = classBodyStart
while (i < src.length && depth > 0) {
    const c = src[i]
    if (c === '{') depth += 1
    else if (c === '}') depth -= 1
    i += 1
}
const classBodyEnd = i - 1
const body = src.slice(classBodyStart, classBodyEnd)

// 3. Walk top-level lines for field declarations. Skip:
//    - constructor(...) blocks (we re-enter via parameter parsing below)
//    - method bodies
//    - blank lines and pure comments
//    Match patterns:
//      `name: Type`
//      `name?: Type`
//      `readonly name: Type`
//      `public name: Type`
// We DO NOT support: nested types, generics with commas, function-typed
// fields. The MVP-recovered shape is "scaffolded entity field" only.
const fields = []
let cursor = 0
let bodyDepth = 0
let inConstructor = false
let lineStart = 0

// First, walk the body to find constructor parameter properties
// (parameters with `public`/`private`/`readonly` modifiers act as
// field declarations in TypeScript).
const ctorMatch = body.match(/constructor\s*\(([^)]*)\)/)
if (ctorMatch) {
    const params = ctorMatch[1]
    // Split on top-level commas (no nested generics at this MVP scope)
    const parts = params.split(/,(?![^<>]*>)/)
    for (const part of parts) {
        const m = part.trim().match(/(?:public|private|protected|readonly)\s+(?:readonly\s+)?(\w+)\s*\??\s*:\s*([\w<>\[\]\s|]+?)(?:\s*=.*)?$/)
        if (m) fields.push({ name: m[1], type: m[2].trim() })
    }
}

// Then walk lines for plain class-body field declarations (anything
// outside constructor or method bodies — i.e. at the class body's
// top level).
const lines = body.split(/\n/)
let braceDepth = 0
for (const raw of lines) {
    const line = raw.trim()
    if (!line || line.startsWith('//') || line.startsWith('/*') || line.startsWith('*')) continue
    if (line.startsWith('constructor')) continue

    // Track {} for skipping method bodies.
    const opens = (line.match(/\{/g) || []).length
    const closes = (line.match(/\}/g) || []).length

    if (braceDepth === 0) {
        // Try to match a field declaration at class top-level.
        const fieldMatch = line.match(/^(?:public\s+|private\s+|protected\s+|readonly\s+|static\s+)*(\w+)\s*\??\s*:\s*([\w<>\[\]\s|]+?)\s*(?:=.*)?[;,]?\s*$/)
        // Reject lines that look like method signatures: ending with ) {
        // or containing ( ... ) before the colon.
        const looksLikeMethod = /\(\s*[^)]*\)\s*[:\{]/.test(line)
        if (fieldMatch && !looksLikeMethod) {
            const name = fieldMatch[1]
            const type = fieldMatch[2].trim()
            // De-dup against constructor-parameter properties
            if (!fields.some((f) => f.name === name)) {
                fields.push({ name, type })
            }
        }
    }

    braceDepth += opens - closes
    if (braceDepth < 0) braceDepth = 0
}

// 4. Heuristic kind classification by path.
let kind = 'Aggregate'
const lower = filePath.toLowerCase()
if (lower.includes('/usecases/') || lower.includes('/use_cases/')) kind = 'Command'
else if (lower.includes('/events/')) kind = 'Event'
else if (lower.includes('/readmodels/') || lower.includes('/read_models/')) kind = 'ReadModel'
// /entities/ → Aggregate (default)

process.stdout.write(JSON.stringify({ kind, name: className, fields }, null, 2))
process.stdout.write('\n')
