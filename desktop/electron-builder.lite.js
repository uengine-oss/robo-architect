// desktop 판의 **lite 프로필** 빌드 — electron-builder.yml(enterprise, 기본) 위에 브랜드와
// macOS 배포 방식만 덮는다. 코드는 같은 것을 싣고, 설치본의 package.json 에
// `roboDesktopProfile: "lite"` 를 구워 앱이 lite 로 돈다(src/main/desktop-profile.ts).
//
//   npm run dist:mac     electron-builder --mac --arm64 --config electron-builder.lite.js
//   npm run dist:win     electron-builder.win.js (이 설정 + out/win/runtime)
'use strict'
const fs = require('fs')
const path = require('path')
const yaml = require('js-yaml') // electron-builder's own YAML reader

const config = yaml.load(fs.readFileSync(path.join(__dirname, 'electron-builder.yml'), 'utf8'))

config.appId = 'org.uengine.robo-architect-lite'
config.productName = 'Robo Architect Lite'
// The installed app's name for Electron (app.getName → ~/Library/Application Support/Robo Architect Lite,
// the "Robo Architect Lite Safe Storage" keychain item). package.json keeps the development name, so a
// development run and an installed copy never share a data folder.
config.extraMetadata = {
  ...(config.extraMetadata || {}),
  productName: 'Robo Architect Lite',
  description: 'Robo Architect Lite — desktop app (Electron shell + host Architect API + Docker stack on Ontological DB).',
  roboDesktopProfile: 'lite',
}

config.win = { ...config.win, artifactName: 'Robo-Architect-Lite-win-${arch}.${ext}' }
config.nsis = { ...config.nsis, artifactName: 'Robo-Architect-Lite-Setup-win-x64.${ext}' }

// macOS (Apple Silicon): a DMG with a fixed name, so the website can link
//   https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest/download/Robo-Architect-Lite-mac-arm64.dmg
// Build: scripts/build-packaged-runtime.sh, then `npm run dist:mac` (scripts/release/README.md).
// No Developer ID: signed ad hoc after packing (scripts/adhoc-sign.js) — Gatekeeper then offers
// "Open Anyway" instead of calling a downloaded copy damaged. A hardened runtime needs entitlements
// (JIT) a real identity would bring, so it stays off with ad-hoc signing.
config.mac = {
  ...config.mac,
  target: [{ target: 'dmg', arch: ['arm64'] }],
  identity: null,
  hardenedRuntime: false,
  gatekeeperAssess: false,
  artifactName: 'Robo-Architect-Lite-mac-${arch}.${ext}',
}
config.afterPack = 'scripts/adhoc-sign.js'
config.dmg = {
  title: 'Robo Architect Lite',
  artifactName: 'Robo-Architect-Lite-mac-${arch}.${ext}',
  icon: 'resources/icons/icon.icns',
  iconSize: 96,
  window: { width: 540, height: 380 },
  contents: [
    { x: 140, y: 200, type: 'file' },
    { x: 400, y: 200, type: 'link', path: '/Applications' },
  ],
}

module.exports = config
