import {
  compileSchema,
  decodeBinarySchema,
  encodeBinarySchema,
  ByteBuffer,
} from 'kiwi-schema'
import { deflateRaw, inflateRaw } from 'pako'

const FIG_KIWI_PRELUDE = 'fig-kiwi'
const FIG_KIWI_VERSION = 15

function parseArchive(buf: Uint8Array) {
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength)
  let offset = 0

  const prelude = String.fromCharCode(...buf.slice(0, FIG_KIWI_PRELUDE.length))
  if (prelude !== FIG_KIWI_PRELUDE) throw new Error(`Bad prelude: ${prelude}`)
  offset += FIG_KIWI_PRELUDE.length

  const version = view.getUint32(offset, true)
  offset += 4

  const files: Uint8Array[] = []
  while (offset + 4 <= buf.length) {
    const size = view.getUint32(offset, true)
    offset += 4
    files.push(buf.slice(offset, offset + size))
    offset += size
  }

  return { version, files }
}

function buildArchive(files: Uint8Array[]): Uint8Array {
  const headerSize = FIG_KIWI_PRELUDE.length + 4
  const totalSize = files.reduce((s, f) => s + 4 + f.byteLength, headerSize)
  const buf = new Uint8Array(totalSize)
  const view = new DataView(buf.buffer)
  const enc = new TextEncoder()

  let offset = enc.encodeInto(FIG_KIWI_PRELUDE, buf).written!
  view.setUint32(offset, FIG_KIWI_VERSION, true)
  offset += 4

  for (const file of files) {
    view.setUint32(offset, file.byteLength, true)
    offset += 4
    buf.set(file, offset)
    offset += file.byteLength
  }

  return buf
}

function extractBase64(value: string, tag: string): string {
  const startMarker = `<!--(${tag})`
  const endMarker = `(/${tag})-->`

  const si = value.indexOf(startMarker)
  if (si !== -1) {
    const ei = value.indexOf(endMarker)
    return value.substring(si + startMarker.length, ei)
  }

  const altStart = `(${tag})`
  const altEnd = `(/${tag})`
  const asi = value.indexOf(altStart)
  if (asi !== -1) {
    const aei = value.indexOf(altEnd)
    return value.substring(asi + altStart.length, aei)
  }

  return value.trim()
}

function parseHTMLClipboard(html: string) {
  const metaStart = '<!--(figmeta)'
  const metaEnd = '(/figmeta)-->'
  const figmaStart = '<!--(figma)'
  const figmaEnd = '(/figma)-->'

  let metaB64: string | null = null
  let figB64: string | null = null

  const msi = html.indexOf(metaStart)
  const fsi = html.indexOf(figmaStart)
  if (msi !== -1 && fsi !== -1) {
    const mei = html.indexOf(metaEnd)
    const fei = html.indexOf(figmaEnd)
    metaB64 = html.substring(msi + metaStart.length, mei)
    figB64 = html.substring(fsi + figmaStart.length, fei)
  }

  if (!metaB64 || !figB64) {
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const metaSpan = doc.querySelector('span[data-metadata]')
    const bufSpan = doc.querySelector('span[data-buffer]')
    if (metaSpan && bufSpan) {
      const metaAttr = metaSpan.getAttribute('data-metadata') || ''
      const bufAttr = bufSpan.getAttribute('data-buffer') || ''
      metaB64 = extractBase64(metaAttr, 'figmeta')
      figB64 = extractBase64(bufAttr, 'figma')
    }
  }

  if (!metaB64 || !figB64) {
    const metaMatch = html.match(/data-metadata="([^"]*)"/)
    const bufMatch = html.match(/data-buffer="([^"]*)"/)
    if (metaMatch && bufMatch) {
      metaB64 = extractBase64(metaMatch[1], 'figmeta')
      figB64 = extractBase64(bufMatch[1], 'figma')
    }
  }

  if (!metaB64 || !figB64) {
    throw new Error('No figma data in HTML')
  }

  const meta = JSON.parse(atob(metaB64))
  const figma = Uint8Array.from(atob(figB64), c => c.charCodeAt(0))
  return { meta, figma }
}

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

function composeHTMLClipboard(meta: any, figma: Uint8Array): string {
  const metaB64 = btoa(JSON.stringify(meta))
  const figB64 = uint8ToBase64(figma)

  return `<meta charset="utf-8" /><meta charset="utf-8" /><span
  data-metadata="<!--(figmeta)${metaB64}(/figmeta)-->"
></span
><span
  data-buffer="<!--(figma)${figB64}(/figma)-->"
></span
><span style="white-space: pre-wrap"></span>`
}

export interface FigmaClipboardData {
  meta: any
  schema: any
  message: any
}

export function readClipboardHTML(html: string): FigmaClipboardData {
  const { meta, figma } = parseHTMLClipboard(html)
  const { files } = parseArchive(figma)

  const [schemaCompressed, dataCompressed] = files
  const schemaBuf = inflateRaw(schemaCompressed)
  const schema = decodeBinarySchema(new ByteBuffer(schemaBuf))
  const compiled = compileSchema(schema)
  const dataBuf = inflateRaw(dataCompressed)
  const message = compiled.decodeMessage(new ByteBuffer(dataBuf))

  return { meta, schema, message }
}

export function writeClipboardHTML(data: FigmaClipboardData): string {
  const { meta, schema, message } = data
  const compiled = compileSchema(schema)

  const schemaBin = encodeBinarySchema(schema)
  const schemaCompressed = deflateRaw(schemaBin)
  const dataBin = compiled.encodeMessage(message)
  const dataCompressed = deflateRaw(dataBin)

  const archive = buildArchive([schemaCompressed, dataCompressed])
  return composeHTMLClipboard(meta, archive)
}

const SCHEMA_KEY = 'figma-schema-cache'

export function getCachedSchema(): any | null {
  const raw = localStorage.getItem(SCHEMA_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

export function cacheSchema(schema: any) {
  localStorage.setItem(SCHEMA_KEY, JSON.stringify(schema))
}

