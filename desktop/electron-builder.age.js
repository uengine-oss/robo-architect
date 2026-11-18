// The Apache AGE edition (macOS Apple Silicon): electron-builder.yml as it is, except
//   - its own app identity, so it installs next to the regular app and never shares its data:
//     "Robo Architect Lite AGE" (org.uengine.robo-architect-lite-age) → its own
//     ~/Library/Application Support/Robo Architect Lite AGE, its own "… Safe Storage" keychain item,
//     its own Figma plugin folder (all of them follow the product name)
//   - its own DMG name, Robo-Architect-Lite-AGE-mac-arm64.dmg — the regular release's fixed name
//     (Robo-Architect-Lite-mac-arm64.dmg, which the website links through releases/latest) is left alone
//   - the runtime folder from out/age/runtime (scripts/build-packaged-runtime.sh --variant age-fabric)
//
//   npm run build && npm run build:figma && env -u ELECTRON_RUN_AS_NODE npx electron-builder --mac --arm64 --config electron-builder.age.js
'use strict'
const fs = require('fs')
const path = require('path')
const yaml = require('js-yaml') // electron-builder's own YAML reader

const PRODUCT = 'Robo Architect Lite AGE'
const config = yaml.load(fs.readFileSync(path.join(__dirname, 'electron-builder.yml'), 'utf8'))
const from = 'out/age/runtime'
const manifestPath = path.join(__dirname, from, 'runtime-manifest.json')
if (!fs.existsSync(manifestPath)) {
  throw new Error(`${manifestPath} is missing — scripts/build-packaged-runtime.sh --variant age-fabric --digests …`)
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
if (manifest.deployVariant !== 'age-fabric' || manifest.composeFile !== 'compose.age-fabric.yml') {
  throw new Error(`${from} is not an age-fabric runtime (deployVariant = ${manifest.deployVariant})`)
}
if (manifest.architect?.python !== 'architect/python/bin/python3') {
  throw new Error(`${from} is not a macOS runtime (architect.python = ${manifest.architect?.python})`)
}

config.appId = 'org.uengine.robo-architect-lite-age'
config.productName = PRODUCT
config.extraMetadata = { ...(config.extraMetadata || {}), productName: PRODUCT }
config.mac = { ...config.mac, artifactName: 'Robo-Architect-Lite-AGE-mac-${arch}.${ext}' }
config.dmg = { ...config.dmg, title: PRODUCT, artifactName: 'Robo-Architect-Lite-AGE-mac-${arch}.${ext}' }
delete config.win
delete config.nsis
const runtime = config.extraResources.find((r) => r.to === 'runtime')
runtime.from = from
module.exports = config
