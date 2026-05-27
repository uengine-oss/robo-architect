#!/usr/bin/env node
// TypeScript AST extractor for /robo-sync (skeleton — feature 029 T018).
//
// Full implementation lands in T045 (US5 phase). When invoked, this stub
// exits with a non-zero status and a clear "not yet implemented" message
// so /robo-sync's flow surface treats it as an unimplemented dependency
// rather than silently producing empty extracts.
//
// Final contract (T045): given a path to a `.ts` file on argv[2], invoke
// `@typescript-eslint/typescript-estree`, walk interfaces / type aliases
// / class members, and emit one JSON document per element on stdout, of
// shape:
//
//   {
//     "kind": "Aggregate" | "Command" | "Event" | "ReadModel",
//     "name": "<element name in source>",
//     "fields": [ { "name": "...", "type": "..." }, ... ]
//   }
//
// The calling skill resolves each `name` to an `elementId` via
// `get_bc_design` (T2) before sending the extract to `propose_sync` (T6).
//
// Run `npm install` inside this directory to pull the parser dependency
// before invoking; package.json pins the version.

const [, , filePath] = process.argv;

if (!filePath) {
    process.stderr.write(
        "usage: node ts_extract.mjs <path-to-ts-file>\n",
    );
    process.exit(2);
}

process.stderr.write(
    "ts_extract.mjs is a skeleton (feature 029 T018). " +
        "Full AST extraction lands in T045 (US5).\n",
);
process.exit(1);
