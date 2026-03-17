import type { WireframeElement } from './types'
import {
  type GUID,
  type NodeChange,
  type Color,
  makeGuid,
  resetGuidCounter,
  makeFrameNode,
  makeRectangleNode,
  makeTextNode,
  makeEllipseNode,
  buildPasteMessage,
  buildMeta,
} from './nodes'
import {
  writeClipboardHTML,
  getCachedSchema,
  type FigmaClipboardData,
} from './figkiwi'

function hexToColor(hex: string | undefined, fallback: Color): Color {
  if (!hex) return fallback
  hex = hex.replace('#', '')
  if (hex.length === 6) hex += 'ff'
  return {
    r: parseInt(hex.slice(0, 2), 16) / 255,
    g: parseInt(hex.slice(2, 4), 16) / 255,
    b: parseInt(hex.slice(4, 6), 16) / 255,
    a: parseInt(hex.slice(6, 8), 16) / 255,
  }
}

const CANVAS_GUID: GUID = { sessionID: 0, localID: 1 }

function convertElement(el: WireframeElement, parentGuid: GUID, index: number, nodes: NodeChange[]): void {
  const guid = makeGuid()

  switch (el.type) {
    case 'frame':
    case 'navbar':
    case 'card':
    case 'sidebar': {
      nodes.push(makeFrameNode(guid, parentGuid, index, {
        name: el.label || el.type.charAt(0).toUpperCase() + el.type.slice(1),
        x: el.x, y: el.y, width: el.width, height: el.height,
        fillColor: hexToColor(el.fillColor, { r: 1, g: 1, b: 1, a: 1 }),
        strokeColor: el.strokeColor ? hexToColor(el.strokeColor, { r: 0, g: 0, b: 0, a: 1 }) : undefined,
        strokeWeight: el.strokeWidth || 0,
        cornerRadius: el.cornerRadius || 0,
      }))
      break
    }
    case 'rectangle': {
      nodes.push(makeRectangleNode(guid, parentGuid, index, {
        name: el.label || 'Rectangle',
        x: el.x, y: el.y, width: el.width, height: el.height,
        fillColor: hexToColor(el.fillColor, { r: 0.85, g: 0.85, b: 0.85, a: 1 }),
        strokeColor: el.strokeColor ? hexToColor(el.strokeColor, { r: 0, g: 0, b: 0, a: 1 }) : undefined,
        strokeWeight: el.strokeWidth || 0,
        cornerRadius: el.cornerRadius || 0,
      }))
      break
    }
    case 'text': {
      nodes.push(makeTextNode(guid, parentGuid, index, {
        name: el.label || 'Text',
        x: el.x, y: el.y, width: el.width, height: el.height,
        text: el.label || 'Text',
        fontSize: el.fontSize || 16,
        color: hexToColor(el.fillColor, { r: 0, g: 0, b: 0, a: 1 }),
        align: el.textAlign || 'LEFT',
      }))
      break
    }
    case 'ellipse': {
      nodes.push(makeEllipseNode(guid, parentGuid, index, {
        name: el.label || 'Ellipse',
        x: el.x, y: el.y, width: el.width, height: el.height,
        fillColor: hexToColor(el.fillColor, { r: 0.85, g: 0.85, b: 0.85, a: 1 }),
        strokeColor: el.strokeColor ? hexToColor(el.strokeColor, { r: 0, g: 0, b: 0, a: 1 }) : undefined,
        strokeWeight: el.strokeWidth || 0,
      }))
      break
    }
    case 'button': {
      const btnFill = hexToColor(el.fillColor, { r: 0.23, g: 0.52, b: 0.96, a: 1 })
      nodes.push(makeFrameNode(guid, parentGuid, index, {
        name: el.label || 'Button',
        x: el.x, y: el.y, width: el.width, height: el.height,
        fillColor: btnFill,
        cornerRadius: el.cornerRadius || 8,
      }))
      // Determine text color based on background brightness
      const brightness = btnFill.r * 0.299 + btnFill.g * 0.587 + btnFill.b * 0.114
      const textColor = brightness > 0.6
        ? { r: 0.12, g: 0.12, b: 0.12, a: 1 }  // dark text on light bg
        : { r: 1, g: 1, b: 1, a: 1 }             // white text on dark bg
      const textGuid = makeGuid()
      nodes.push(makeTextNode(textGuid, guid, 0, {
        name: 'Button Label',
        x: 0, y: 0, width: el.width, height: el.height,
        text: el.label || 'Button',
        fontSize: el.fontSize || 14,
        color: textColor,
        align: 'CENTER', verticalAlign: 'CENTER',
      }))
      break
    }
    case 'input': {
      nodes.push(makeFrameNode(guid, parentGuid, index, {
        name: el.label || 'Input',
        x: el.x, y: el.y, width: el.width, height: el.height,
        fillColor: { r: 1, g: 1, b: 1, a: 1 },
        strokeColor: { r: 0.8, g: 0.8, b: 0.8, a: 1 },
        strokeWeight: 1,
        cornerRadius: el.cornerRadius || 4,
      }))
      const placeholderGuid = makeGuid()
      nodes.push(makeTextNode(placeholderGuid, guid, 0, {
        name: 'Placeholder',
        x: 12, y: 0, width: el.width - 24, height: el.height,
        text: el.label || 'Placeholder...',
        fontSize: el.fontSize || 14,
        color: { r: 0.6, g: 0.6, b: 0.6, a: 1 },
        verticalAlign: 'CENTER',
      }))
      break
    }
  }

  if (el.children) {
    el.children.forEach((child, i) => {
      convertElement(child, guid, i, nodes)
    })
  }
}

export function elementsToFigmaClipboard(elements: WireframeElement[]): string {
  const schema = getCachedSchema()
  if (!schema) {
    throw new Error('No Figma schema cached. Please capture schema first.')
  }

  resetGuidCounter()

  const pasteID = Math.floor(Math.random() * 2147483647)
  const fileKey = generateFileKey()

  const designNodes: NodeChange[] = []
  elements.forEach((el, i) => {
    convertElement(el, CANVAS_GUID, i, designNodes)
  })

  const message = buildPasteMessage(designNodes, pasteID, fileKey)
  const meta = buildMeta(pasteID, fileKey)
  const data: FigmaClipboardData = { meta, schema, message }
  return writeClipboardHTML(data)
}

function generateFileKey(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let key = ''
  for (let i = 0; i < 22; i++) key += chars[Math.floor(Math.random() * chars.length)]
  return key
}

export async function copyToClipboard(html: string): Promise<void> {
  const blob = new Blob([html], { type: 'text/html' })
  const textBlob = new Blob(['Figma wireframe data'], { type: 'text/plain' })
  const item = new ClipboardItem({ 'text/html': blob, 'text/plain': textBlob })
  await navigator.clipboard.write([item])
}
