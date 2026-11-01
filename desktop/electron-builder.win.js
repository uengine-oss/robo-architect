// The Windows x64 installer, cross-built on a Mac: electron-builder.yml as it is, except that the
// runtime folder comes from out/win/runtime (scripts/build-packaged-runtime-win.sh) — resources/runtime
// holds the macOS runtime. No wine: win.signAndEditExecutable is off, and on macOS electron-builder
// reads the NSIS uninstaller out of the installer instead of running it.
//
//   npm run build && env -u ELECTRON_RUN_AS_NODE npx electron-builder --win --x64 --config electron-builder.win.js
'use strict'
const fs = require('fs')
const path = require('path')
const yaml = require('js-yaml') // electron-builder's own YAML reader

const config = yaml.load(fs.readFileSync(path.join(__dirname, 'electron-builder.yml'), 'utf8'))
const from = 'out/win/runtime'
const manifestPath = path.join(__dirname, from, 'runtime-manifest.json')
if (!fs.existsSync(manifestPath)) {
  throw new Error(`${manifestPath} is missing — scripts/build-packaged-runtime-win.sh (--manifest-only once the images are there)`)
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
if (manifest.architect?.python !== 'architect/python/python.exe' ||
    !fs.existsSync(path.join(__dirname, from, manifest.architect.python))) {
  throw new Error(`${from} is not a Windows runtime (architect.python = ${manifest.architect?.python})`)
}
const runtime = config.extraResources.find((r) => r.to === 'runtime')
runtime.from = from
module.exports = config
