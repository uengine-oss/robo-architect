export interface GUID {
  sessionID: number
  localID: number
}

export interface Color {
  r: number
  g: number
  b: number
  a: number
}

export interface Vector {
  x: number
  y: number
}

export interface Matrix {
  m00: number
  m01: number
  m02: number
  m10: number
  m11: number
  m12: number
}

export interface Paint {
  type: string
  color?: Color
  opacity?: number
  visible?: boolean
  blendMode?: string
}

export interface NodeChange {
  guid: GUID
  phase?: string
  parentIndex?: { guid: GUID; position: string }
  type: string
  name?: string
  visible?: boolean
  opacity?: number
  size?: Vector
  transform?: Matrix
  fillPaints?: Paint[]
  strokePaints?: Paint[]
  strokeWeight?: number
  strokeAlign?: string
  strokeJoin?: string
  cornerRadius?: number
  blendMode?: string
  stackChildAlignSelf?: string
  stackMode?: string
  stackSpacing?: number
  stackHorizontalPadding?: number
  stackVerticalPadding?: number
  stackPaddingRight?: number
  stackPaddingBottom?: number
  stackPrimarySizing?: string
  stackCounterSizing?: string
  stackCounterAlignItems?: string
  frameMaskDisabled?: boolean
  textData?: any
  fontSize?: number
  fontName?: any
  textAlignHorizontal?: string
  textAlignVertical?: string
  textAutoResize?: string
  autoRename?: boolean
  textTracking?: number
  lineHeight?: any
  letterSpacing?: any
  fontVariantCommonLigatures?: boolean
  fontVariantContextualLigatures?: boolean
  textUserLayoutVersion?: number
  textBidiVersion?: number
  stackChildPrimaryGrow?: number
  backgroundOpacity?: number
  backgroundEnabled?: boolean
  internalOnly?: boolean
  horizontalConstraint?: string
  verticalConstraint?: string
  [key: string]: any
}

let localIdCounter = 100
const SESSION_ID = 312

export function resetGuidCounter() {
  localIdCounter = 100
}

export function makeGuid(): GUID {
  return { sessionID: SESSION_ID, localID: localIdCounter++ }
}

export function sortPosition(index: number): string {
  return String.fromCharCode(33 + index)
}

export function makeTransform(x: number, y: number): Matrix {
  return { m00: 1, m01: 0, m02: x, m10: 0, m11: 1, m12: y }
}

function solidPaint(color: Color, opacity = 1): Paint {
  return { type: 'SOLID', color, opacity, visible: true, blendMode: 'NORMAL' }
}

export function makeDocumentNode(): NodeChange {
  return {
    guid: { sessionID: 0, localID: 0 },
    phase: 'CREATED',
    type: 'DOCUMENT',
    name: 'Document',
    visible: true,
    opacity: 1,
    transform: makeTransform(0, 0),
  }
}

export function makeCanvasNode(name = 'Page 1'): NodeChange {
  return {
    guid: { sessionID: 0, localID: 1 },
    phase: 'CREATED',
    parentIndex: { guid: { sessionID: 0, localID: 0 }, position: '!' },
    type: 'CANVAS',
    name,
    visible: true,
    opacity: 1,
    transform: makeTransform(0, 0),
    backgroundOpacity: 1,
    backgroundEnabled: true,
  }
}

export function makeInternalCanvas(): NodeChange {
  return {
    guid: { sessionID: 20002313, localID: 2 },
    phase: 'CREATED',
    parentIndex: { guid: { sessionID: 0, localID: 0 }, position: '"' },
    type: 'CANVAS',
    name: 'Internal Only Canvas',
    visible: false,
    opacity: 1,
    transform: makeTransform(0, 0),
    backgroundOpacity: 1,
    backgroundEnabled: false,
    internalOnly: true,
  }
}

export function makeFrameNode(
  guid: GUID, parentGuid: GUID, index: number,
  opts: {
    name?: string; x?: number; y?: number; width?: number; height?: number
    fillColor?: Color; strokeColor?: Color; strokeWeight?: number; cornerRadius?: number
    autoLayout?: boolean; layoutDirection?: 'HORIZONTAL' | 'VERTICAL'
    spacing?: number; padding?: number
  } = {}
): NodeChange {
  const {
    name = 'Frame', x = 0, y = 0, width = 200, height = 200,
    fillColor = { r: 1, g: 1, b: 1, a: 1 }, strokeColor, strokeWeight = 0,
    cornerRadius = 0, autoLayout = false, layoutDirection = 'VERTICAL',
    spacing = 0, padding = 0,
  } = opts

  const node: NodeChange = {
    guid, phase: 'CREATED',
    parentIndex: { guid: parentGuid, position: sortPosition(index) },
    type: 'FRAME', name, visible: true, opacity: 1,
    size: { x: width, y: height },
    transform: makeTransform(x, y),
    strokeWeight: strokeWeight || 0, strokeAlign: 'CENTER', strokeJoin: 'MITER',
    fillPaints: [solidPaint(fillColor)],
    stackChildAlignSelf: 'AUTO',
    frameMaskDisabled: true,
  }

  if (strokeColor && strokeWeight > 0) node.strokePaints = [solidPaint(strokeColor)]
  if (cornerRadius > 0) node.cornerRadius = cornerRadius
  if (autoLayout) {
    node.stackMode = layoutDirection
    node.stackSpacing = spacing
    node.stackHorizontalPadding = padding
    node.stackVerticalPadding = padding
    node.stackPaddingRight = padding
    node.stackPaddingBottom = padding
    node.stackPrimarySizing = 'AUTO'
    node.stackCounterSizing = 'AUTO'
    node.stackCounterAlignItems = 'CENTER'
  }

  return node
}

export function makeRectangleNode(
  guid: GUID, parentGuid: GUID, index: number,
  opts: {
    name?: string; x?: number; y?: number; width?: number; height?: number
    fillColor?: Color; strokeColor?: Color; strokeWeight?: number; cornerRadius?: number
  } = {}
): NodeChange {
  const {
    name = 'Rectangle', x = 0, y = 0, width = 100, height = 100,
    fillColor = { r: 0.85, g: 0.85, b: 0.85, a: 1 }, strokeColor, strokeWeight = 0, cornerRadius = 0,
  } = opts

  const node: NodeChange = {
    guid, phase: 'CREATED',
    parentIndex: { guid: parentGuid, position: sortPosition(index) },
    type: 'RECTANGLE', name, visible: true, opacity: 1,
    size: { x: width, y: height },
    transform: makeTransform(x, y),
    strokeWeight: strokeWeight || 0, strokeAlign: 'CENTER', strokeJoin: 'MITER',
    fillPaints: [solidPaint(fillColor)],
    horizontalConstraint: 'MIN', verticalConstraint: 'MIN',
  }

  if (strokeColor && strokeWeight > 0) node.strokePaints = [solidPaint(strokeColor)]
  if (cornerRadius > 0) node.cornerRadius = cornerRadius
  return node
}

export function makeTextNode(
  guid: GUID, parentGuid: GUID, index: number,
  opts: {
    name?: string; x?: number; y?: number; width?: number; height?: number
    text?: string; fontSize?: number; fontFamily?: string; fontStyle?: string
    color?: Color; align?: string; verticalAlign?: string
  } = {}
): NodeChange {
  const {
    name = 'Text', x = 0, y = 0, width = 100, height = 24,
    text = 'Text', fontSize = 16, fontFamily = 'Inter', fontStyle = 'Regular',
    color = { r: 0, g: 0, b: 0, a: 1 }, align = 'LEFT', verticalAlign = 'TOP',
  } = opts

  return {
    guid, phase: 'CREATED',
    parentIndex: { guid: parentGuid, position: sortPosition(index) },
    type: 'TEXT', name, visible: true, opacity: 1,
    size: { x: width, y: height },
    transform: makeTransform(x, y),
    strokeWeight: 0, strokeAlign: 'CENTER', strokeJoin: 'MITER',
    fillPaints: [solidPaint(color)],
    fontSize,
    fontName: { family: fontFamily, style: fontStyle, postscript: '' },
    textAlignHorizontal: align,
    textAlignVertical: verticalAlign,
    textAutoResize: 'WIDTH_AND_HEIGHT',
    autoRename: true,
    textTracking: 0,
    lineHeight: { value: 0, units: 'RAW' },
    letterSpacing: { value: 0, units: 'PIXELS' },
    fontVariantCommonLigatures: true,
    fontVariantContextualLigatures: true,
    textUserLayoutVersion: 0,
    textBidiVersion: 0,
    stackChildPrimaryGrow: 0,
    textData: {
      characters: text,
      lines: [{
        lineType: 'PLAIN', styleId: 0, indentationLevel: 0,
        sourceDirectionality: 'AUTO', listStartOffset: 0, isFirstLineOfList: false,
      }],
    },
  }
}

export function makeEllipseNode(
  guid: GUID, parentGuid: GUID, index: number,
  opts: {
    name?: string; x?: number; y?: number; width?: number; height?: number
    fillColor?: Color; strokeColor?: Color; strokeWeight?: number
  } = {}
): NodeChange {
  const {
    name = 'Ellipse', x = 0, y = 0, width = 100, height = 100,
    fillColor = { r: 0.85, g: 0.85, b: 0.85, a: 1 }, strokeColor, strokeWeight = 0,
  } = opts

  const node: NodeChange = {
    guid, phase: 'CREATED',
    parentIndex: { guid: parentGuid, position: sortPosition(index) },
    type: 'ELLIPSE', name, visible: true, opacity: 1,
    size: { x: width, y: height },
    transform: makeTransform(x, y),
    strokeWeight: strokeWeight || 0, strokeAlign: 'CENTER', strokeJoin: 'MITER',
    fillPaints: [solidPaint(fillColor)],
    horizontalConstraint: 'MIN', verticalConstraint: 'MIN',
  }

  if (strokeColor && strokeWeight > 0) node.strokePaints = [solidPaint(strokeColor)]
  return node
}

export function buildPasteMessage(designNodes: NodeChange[], pasteID: number, pasteFileKey: string) {
  const allNodes: NodeChange[] = [
    makeDocumentNode(),
    makeCanvasNode(),
    ...designNodes,
    makeInternalCanvas(),
  ]

  return {
    type: 'NODE_CHANGES',
    sessionID: 0,
    ackID: 0,
    pasteID,
    pasteFileKey,
    pastePageId: { sessionID: 0, localID: 1 },
    isCut: false,
    pasteEditorType: 'DESIGN',
    nodeChanges: allNodes,
    blobs: [],
  }
}

export function buildMeta(pasteID: number, fileKey: string) {
  return { fileKey, pasteID, dataType: 'scene' }
}
