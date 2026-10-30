// App icons from the one-colour brand artwork (resources/brand/ra-box*.svg, made by
// scripts/make-brand.py), rendered by Electron itself — the same way Ontological Studio
// makes its icons (its scripts/make-icon.js), so the two apps' icons match.
//   env -u ELECTRON_RUN_AS_NODE npx electron scripts/make-icon.js
// Writes resources/icons/
//   icon_1024x1024.png … icon_16x16.png, icon.png (512)   macOS icon grid (824² tile, radius 185)
//   robo-architect.iconset/ → icon.icns (iconutil, macOS only)  ·  icon.ico (Python Pillow)
'use strict'
const { app, BrowserWindow } = require('electron')
const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
const ICONS = path.join(ROOT, 'resources', 'icons')
const BOX = fs.readFileSync(path.join(ROOT, 'resources', 'brand', 'ra-box.svg'), 'utf8')
const BOX_SMALL = fs.readFileSync(path.join(ROOT, 'resources', 'brand', 'ra-box-small.svg'), 'utf8')

let win = null
async function render(html, width, height = width) {
  // one window for every render: closing the last window would start the app's quit
  if (!win) win = new BrowserWindow({ show: false, width, height, transparent: true, frame: false, webPreferences: { offscreen: true } })
  win.setContentSize(width, height)
  await win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)
  await new Promise((r) => setTimeout(r, 300))
  const img = await win.webContents.capturePage({ x: 0, y: 0, width, height })
  return img.resize({ width, height, quality: 'best' }) // capture is at device scale
}

// the app icon is the box itself on the macOS tile grid (824² at 100,100; the box's corner is
// the tile's): a white plate under it turns the cut-out mark white
const page = (box) => `<!doctype html><html><head><style>
  html,body{margin:0;width:1024px;height:1024px;background:transparent;overflow:hidden}
  .tile{position:absolute;left:100px;top:100px;width:824px;height:824px}
  .tile .plate{position:absolute;inset:24px;border-radius:160px;background:#fff}
  .tile svg{position:absolute;inset:0;width:824px;height:824px}
</style></head><body><div class="tile"><div class="plate"></div>${box}</div></body></html>`

app.whenReady().then(async () => {
  try {
    fs.mkdirSync(ICONS, { recursive: true })
    const big = await render(page(BOX), 1024)
    const small = await render(page(BOX_SMALL), 1024) // wider gaps survive at 16–32 px
    const sizes = [1024, 512, 256, 128, 64, 48, 32, 16]
    for (const s of sizes) {
      const src = s <= 32 ? small : big
      fs.writeFileSync(path.join(ICONS, `icon_${s}x${s}.png`), src.resize({ width: s, height: s, quality: 'best' }).toPNG())
    }
    fs.writeFileSync(path.join(ICONS, 'icon.png'), big.resize({ width: 512, height: 512, quality: 'best' }).toPNG())
    if (process.platform === 'darwin') {
      const set = path.join(ICONS, 'robo-architect.iconset')
      fs.rmSync(set, { recursive: true, force: true })
      fs.mkdirSync(set)
      for (const [s, name] of [[16, '16x16'], [32, '16x16@2x'], [32, '32x32'], [64, '32x32@2x'], [128, '128x128'], [256, '128x128@2x'], [256, '256x256'], [512, '256x256@2x'], [512, '512x512'], [1024, '512x512@2x']]) {
        const src = s <= 32 ? small : big
        fs.writeFileSync(path.join(set, `icon_${name}.png`), src.resize({ width: s, height: s, quality: 'best' }).toPNG())
      }
      execFileSync('iconutil', ['-c', 'icns', set, '-o', path.join(ICONS, 'icon.icns')])
    }
    execFileSync('python3', ['-c', [
      'from PIL import Image', 'import sys',
      'im = Image.open(sys.argv[1])',
      'im.save(sys.argv[2], sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])',
    ].join('\n'), path.join(ICONS, 'icon_1024x1024.png'), path.join(ICONS, 'icon.ico')])
    console.log('icons →', ICONS)
  } catch (e) {
    console.error(e)
    process.exitCode = 1
  }
  app.quit()
})
