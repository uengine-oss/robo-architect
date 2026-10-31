// electron-builder afterPack: sign the whole .app ad hoc (macOS only) — the same as Ontological Studio.
//
// With mac.identity: null electron-builder signs nothing, so the bundle keeps only the linker's
// signature on the Electron executable, with no sealed resources. A downloaded (quarantined) arm64
// copy then fails Gatekeeper as "damaged" and cannot be opened at all. With a valid ad-hoc signature
// it is an unidentified developer's app instead: System Settings › Privacy & Security › Open Anyway
// lets it run. Runs before the dmg target is built, so the DMG carries the signed app.
//
// The bundled CPython and its extension modules (Resources/runtime/architect/python) keep their own
// signatures and are sealed as resources of the app.
'use strict'
const path = require('path')
const { execFileSync } = require('child_process')

exports.default = async function adhocSign(context) {
  if (context.electronPlatformName !== 'darwin') return
  const app = path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`)
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', app], { stdio: 'inherit' })
  execFileSync('codesign', ['--verify', '--deep', '--strict', app], { stdio: 'inherit' })
}
