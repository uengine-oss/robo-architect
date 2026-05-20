// Minimal plugin — just show UI
const html = '<h2 style="padding:20px">RoboArchitect Sync</h2><p style="padding:0 20px">Plugin loaded OK</p>'
figma.showUI(html, { width: 320, height: 200 })
figma.ui.postMessage({ type: 'READY' })
