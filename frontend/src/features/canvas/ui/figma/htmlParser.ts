import type { WireframeElement } from './types'

/**
 * Improved HTML → WireframeElement[] parser.
 *
 * Fixes over figma-integration original:
 * 1. Semantic HTML tags (MAIN, SECTION, HEADER, NAV, FOOTER, FORM, FIELDSET,
 *    ARTICLE, ASIDE, FIGURE) are recursed into — not just DIV/SPAN.
 * 2. Added handlers: wf-grid, wf-col-*, wf-label, wf-badge, wf-state,
 *    wf-empty (nested __title/__desc), wf-subtitle, TEXTAREA, SELECT.
 * 3. Flex-row detection is less strict (no align-items requirement).
 * 4. CSS-grid layout detection for wf-grid containers.
 */

let importIdCounter = 0
function nextId(): string {
  return `imp-${++importIdCounter}`
}

interface Ctx {
  x: number
  y: number
  maxWidth: number
}

// Tags that should be recursed into like DIV/SPAN
const CONTAINER_TAGS = new Set([
  'DIV', 'SPAN', 'MAIN', 'SECTION', 'HEADER', 'NAV', 'FOOTER',
  'FORM', 'FIELDSET', 'ARTICLE', 'ASIDE', 'FIGURE', 'FIGCAPTION',
  'UL', 'OL', 'LI', 'DL', 'DT', 'DD', 'DETAILS', 'SUMMARY',
])

export function parseHtmlWireframe(html: string): WireframeElement[] {
  importIdCounter = 0
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const root = doc.querySelector('.wf-root')
  return walkChildren(root || doc.body, { x: 0, y: 0, maxWidth: 1100 })
}

function walkChildren(parent: Element, ctx: Ctx): WireframeElement[] {
  const elements: WireframeElement[] = []
  let cursorY = ctx.y

  for (const child of Array.from(parent.children)) {
    const tag = child.tagName
    if (tag === 'STYLE' || tag === 'SCRIPT' || tag === 'LINK' || tag === 'META') continue
    if (child.nodeType !== 1) continue

    const result = convertElement(child, { x: ctx.x, y: cursorY, maxWidth: ctx.maxWidth })
    if (result) {
      elements.push(result)
      cursorY += result.height + 8
    }
  }

  return elements
}

function convertElement(el: Element, ctx: Ctx): WireframeElement | null {
  const cls = el.className?.toString?.() || ''
  const style = parseInlineStyle((el as HTMLElement).style?.cssText || el.getAttribute('style') || '')

  // ── wf-* class-based detection (ordered by specificity) ──
  if (cls.includes('wf-appbar')) return convertAppbar(el, ctx)
  if (cls.includes('wf-card')) return convertCard(el, ctx, style)
  if (cls.includes('wf-table') && el.tagName === 'TABLE') return convertTable(el, ctx)
  if (cls.includes('wf-table__toolbar')) return convertToolbar(el, ctx, style)
  if (cls.includes('wf-pagination')) return convertPagination(el, ctx)
  if (cls.includes('wf-grid')) return convertGrid(el, ctx, style)
  if (cls.includes('wf-btn--primary')) return convertButton(el, ctx, '#1890ff')
  if (cls.includes('wf-btn')) return convertButton(el, ctx, '#f5f5f5')
  if (cls.includes('wf-input') && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT'))
    return convertInput(el, ctx, style)
  if (cls.includes('wf-actions')) return convertActions(el, ctx)
  if (cls.includes('wf-chip')) return convertChip(el, ctx, style)
  if (cls.includes('wf-badge')) return convertBadge(el, ctx, style)
  if (cls.includes('wf-state')) {
    const stateText = el.textContent?.trim() || ''
    if (!stateText) return null  // Skip empty state placeholders
    return convertState(el, ctx, style)
  }
  if (cls.includes('wf-empty')) return convertEmpty(el, ctx, style)
  if (cls.includes('wf-title') || cls.includes('wf-card__title')) return convertText(el, ctx, style)
  if (cls.includes('wf-subtitle')) return convertText(el, ctx, { ...style, 'font-size': style['font-size'] || '12px', color: style.color || '#8c8c8c' })
  if (cls.includes('wf-label')) return convertLabel(el, ctx, style)

  // ── Tag-based detection ──
  if (el.tagName === 'INPUT' && (el.getAttribute('type') === 'checkbox' || el.getAttribute('type') === 'radio')) {
    return convertCheckbox(el, ctx)
  }

  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
    return convertInput(el, ctx, style)
  }

  if (el.tagName === 'BUTTON') {
    return convertButton(el, ctx, '#f5f5f5')
  }

  if (el.tagName === 'TABLE') {
    return convertTable(el, ctx)
  }

  if (el.tagName === 'LABEL') {
    return convertLabel(el, ctx, style)
  }

  // ── Container tags → recurse ──
  if (CONTAINER_TAGS.has(el.tagName)) {
    // Text-only leaf
    const directText = getDirectText(el).trim()
    if (directText && el.children.length === 0) {
      return makeText(directText, ctx, style)
    }

    // Flex-row detection: inline style OR known CSS-flex classes
    const isFlexRow = (style.display === 'flex' && style['flex-direction'] !== 'column')
      || cls.includes('wf-table__toolbar')
      || cls.includes('wf-pagination')

    if (isFlexRow) {
      return convertFlexRow(el, ctx, style)
    }

    // Recurse
    const children = walkChildren(el, ctx)
    if (children.length === 1) return children[0]
    if (children.length > 0) {
      const bounds = getBounds(children)
      return {
        id: nextId(),
        type: 'frame',
        x: ctx.x,
        y: ctx.y,
        width: bounds.width || ctx.maxWidth,
        height: bounds.height,
        fillColor: style['background'] || style['background-color'] || undefined,
        children: children.map(c => ({ ...c, x: c.x - ctx.x, y: c.y - ctx.y })),
      }
    }

    return null
  }

  // Table sub-elements handled by convertTable
  if (['THEAD', 'TBODY', 'TR', 'TH', 'TD', 'TFOOT'].includes(el.tagName)) {
    return null
  }

  // Fallback: text content
  const text = getDirectText(el).trim() || el.textContent?.trim() || ''
  if (text) {
    return makeText(text, ctx, style)
  }

  return null
}

// ── Component converters ──

function convertAppbar(el: Element, ctx: Ctx): WireframeElement {
  const children: WireframeElement[] = []
  let cursorX = 24

  // Walk all descendants looking for title and actions
  const titleEl = el.querySelector('.wf-title')
  if (titleEl) {
    children.push({
      id: nextId(), type: 'text',
      x: cursorX, y: 16, width: 200, height: 24,
      label: titleEl.textContent?.trim() || 'Title',
      fontSize: 20, fillColor: '#000000',
    })
    cursorX += 220
  }

  const subtitleEl = el.querySelector('.wf-subtitle')
  if (subtitleEl) {
    children.push({
      id: nextId(), type: 'text',
      x: 24, y: 36, width: 200, height: 16,
      label: subtitleEl.textContent?.trim() || '',
      fontSize: 12, fillColor: '#8c8c8c',
    })
  }

  // Right-aligned action buttons
  const actionContainer = el.querySelector('.wf-actions, .wf-appbar__right')
  if (actionContainer) {
    let btnX = ctx.maxWidth - 24
    const buttons = actionContainer.querySelectorAll('.wf-btn')
    for (const btn of Array.from(buttons).reverse()) {
      const label = btn.textContent?.trim() || 'Button'
      const w = Math.max(80, label.length * 10 + 32)
      btnX -= w + 8
      const isPrimary = btn.className.includes('wf-btn--primary')
      children.push({
        id: nextId(), type: 'button',
        x: btnX, y: 12, width: w, height: 32,
        label,
        fillColor: isPrimary ? '#1890ff' : '#f5f5f5',
        cornerRadius: 4, fontSize: 14,
      })
    }
  }

  return {
    id: nextId(), type: 'navbar',
    x: ctx.x, y: ctx.y, width: ctx.maxWidth, height: 56,
    fillColor: '#FFFFFF', strokeColor: '#f0f0f0', strokeWidth: 1,
    label: 'AppBar', children,
  }
}

function convertCard(el: Element, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const marginTop = parsePixels(style['margin-top']) || 0
  const innerChildren: WireframeElement[] = []
  let innerY = 0

  for (const child of Array.from(el.children)) {
    const cls = child.className?.toString?.() || ''
    if (cls.includes('wf-card__header')) {
      const title = child.querySelector('.wf-card__title')?.textContent?.trim() || ''
      if (title) {
        innerChildren.push({
          id: nextId(), type: 'text',
          x: 24, y: 20, width: ctx.maxWidth - 48, height: 20,
          label: title, fontSize: 16, fillColor: '#000000',
        })
      }
      // Badge in header
      const badge = child.querySelector('.wf-badge')
      if (badge) {
        const badgeText = badge.textContent?.trim() || ''
        if (badgeText) {
          innerChildren.push({
            id: nextId(), type: 'button',
            x: ctx.maxWidth - 80, y: 18, width: Math.max(40, badgeText.length * 9 + 16), height: 24,
            label: badgeText, fillColor: '#f0f0f0', cornerRadius: 12, fontSize: 12,
          })
        }
      }
      // Actions in header
      const headerActions = child.querySelector('.wf-actions')
      if (headerActions) {
        let btnX = ctx.maxWidth - 24
        for (const btn of Array.from(headerActions.children).reverse()) {
          const label = btn.textContent?.trim() || ''
          if (!label) continue
          const w = Math.max(60, label.length * 9 + 20)
          btnX -= w + 8
          innerChildren.push({
            id: nextId(), type: 'button',
            x: btnX, y: 18, width: w, height: 24,
            label, fillColor: '#f0f0f0', cornerRadius: 12, fontSize: 12,
          })
        }
      }
      innerY = 52
    } else if (cls.includes('wf-card__body')) {
      const bodyElements = walkChildren(child, { x: 20, y: innerY + 20, maxWidth: ctx.maxWidth - 40 })
      for (const be of bodyElements) innerChildren.push(be)
      const bodyBounds = getBounds(bodyElements)
      innerY = bodyBounds.bottom + 24
    } else {
      const converted = convertElement(child, { x: 20, y: innerY, maxWidth: ctx.maxWidth - 40 })
      if (converted) {
        innerChildren.push(converted)
        innerY += converted.height + 8
      }
    }
  }

  const height = Math.max(innerY + 24, 100)

  return {
    id: nextId(), type: 'card',
    x: ctx.x, y: ctx.y + marginTop,
    width: ctx.maxWidth, height,
    fillColor: '#FFFFFF', strokeColor: '#f0f0f0', strokeWidth: 1,
    cornerRadius: 8, label: 'Card',
    children: innerChildren,
  }
}

function convertTable(el: Element, ctx: Ctx): WireframeElement {
  const children: WireframeElement[] = []
  const colWidths: number[] = []
  const totalWidth = ctx.maxWidth

  const ths = el.querySelectorAll('thead th')
  if (ths.length > 0) {
    let remainingWidth = totalWidth
    let flexCols = 0
    for (const th of Array.from(ths)) {
      const w = parsePixels((th as HTMLElement).style?.width || '')
      if (w) { colWidths.push(w); remainingWidth -= w }
      else { colWidths.push(0); flexCols++ }
    }
    const flexWidth = flexCols > 0 ? remainingWidth / flexCols : 0
    for (let i = 0; i < colWidths.length; i++) {
      if (colWidths[i] === 0) colWidths[i] = flexWidth
    }
  }

  const rowHeight = 40
  let curY = 0

  // Header
  if (ths.length > 0) {
    children.push({
      id: nextId(), type: 'rectangle',
      x: 0, y: curY, width: totalWidth, height: rowHeight,
      fillColor: '#fafafa', label: 'Table Header BG',
    })
    let colX = 0
    for (let i = 0; i < ths.length; i++) {
      const th = ths[i]
      const thCheckbox = th.querySelector('input[type="checkbox"], input[type="radio"]')
      if (thCheckbox) {
        const isRadio = thCheckbox.getAttribute('type') === 'radio'
        children.push({
          id: nextId(), type: 'frame',
          x: colX + Math.floor((colWidths[i] - 16) / 2), y: curY + 12,
          width: 16, height: 16,
          fillColor: '#FFFFFF', strokeColor: '#d9d9d9', strokeWidth: 1,
          cornerRadius: isRadio ? 8 : 3,
          label: isRadio ? 'Radio' : 'Checkbox',
        })
      } else {
        const text = th.textContent?.trim() || ''
        children.push({
          id: nextId(), type: 'text',
          x: colX + 8, y: curY + 10, width: colWidths[i] - 16, height: 20,
          label: text, fontSize: 14, fillColor: '#595959',
        })
      }
      colX += colWidths[i]
    }
    curY += rowHeight
  }

  // Data rows
  const rows = el.querySelectorAll('tbody > tr')
  for (const row of Array.from(rows)) {
    if ((row as HTMLElement).style?.display === 'none') continue
    const cells = row.querySelectorAll('td')
    if (cells.length === 0) continue

    const firstCell = cells[0]
    if (firstCell.getAttribute('colspan')) {
      const emptyDiv = firstCell.querySelector('.wf-empty')
      if (emptyDiv) {
        children.push({
          id: nextId(), type: 'text',
          x: 0, y: curY + 16, width: totalWidth, height: 24,
          label: emptyDiv.textContent?.trim() || 'No data',
          fontSize: 16, fillColor: '#bfbfbf', textAlign: 'CENTER',
        })
        curY += 64
        continue
      }
    }

    let colX = 0
    for (let i = 0; i < cells.length; i++) {
      const cell = cells[i]
      const colW = colWidths[i] || 150

      const checkbox = cell.querySelector('input[type="checkbox"], input[type="radio"]')
      const chip = cell.querySelector('.wf-chip')
      const badge = cell.querySelector('.wf-badge')
      const btn = cell.querySelector('.wf-btn')

      if (checkbox) {
        const isRadio = checkbox.getAttribute('type') === 'radio'
        children.push({
          id: nextId(), type: 'frame',
          x: colX + Math.floor((colW - 16) / 2), y: curY + 12,
          width: 16, height: 16,
          fillColor: '#FFFFFF', strokeColor: '#d9d9d9', strokeWidth: 1,
          cornerRadius: isRadio ? 8 : 3,
          label: isRadio ? 'Radio' : 'Checkbox',
        })
      } else if (chip) {
        const chipStyle = parseInlineStyle(chip.getAttribute('style') || '')
        children.push({
          id: nextId(), type: 'button',
          x: colX + 8, y: curY + 8, width: colW - 16, height: 24,
          label: chip.textContent?.trim() || '',
          fillColor: chipStyle['background'] || '#e6f7ff', cornerRadius: 12, fontSize: 13,
        })
      } else if (badge) {
        children.push({
          id: nextId(), type: 'button',
          x: colX + 8, y: curY + 8, width: colW - 16, height: 24,
          label: badge.textContent?.trim() || '',
          fillColor: '#f0f0f0', cornerRadius: 12, fontSize: 13,
        })
      } else if (btn) {
        children.push({
          id: nextId(), type: 'button',
          x: colX + 8, y: curY + 8, width: 60, height: 24,
          label: btn.textContent?.trim() || 'Button',
          fillColor: '#f5f5f5', cornerRadius: 4, fontSize: 13,
        })
      } else {
        const text = cell.textContent?.trim() || ''
        if (text) {
          children.push({
            id: nextId(), type: 'text',
            x: colX + 8, y: curY + 10, width: colW - 16, height: 20,
            label: text, fontSize: 14, fillColor: '#000000',
          })
        }
      }
      colX += colW
    }

    // Row separator
    children.push({
      id: nextId(), type: 'rectangle',
      x: 0, y: curY + rowHeight - 1, width: totalWidth, height: 1,
      fillColor: '#f0f0f0',
    })
    curY += rowHeight
  }

  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y, width: totalWidth, height: curY,
    fillColor: '#FFFFFF', label: 'Table', children,
  }
}

function convertToolbar(el: Element, ctx: Ctx, _style: Record<string, string>): WireframeElement {
  // Table toolbar — horizontal flex layout
  return convertFlexRow(el, ctx, { display: 'flex' }) || {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y, width: ctx.maxWidth, height: 40,
    label: 'Toolbar',
  }
}

function convertGrid(el: Element, ctx: Ctx, _style: Record<string, string>): WireframeElement {
  const children: WireframeElement[] = []
  const gap = 10
  let cursorX = 0
  let cursorY = 0
  let rowMaxHeight = 0

  for (const child of Array.from(el.children)) {
    const cls = child.className?.toString?.() || ''
    let colSpan = 12
    if (cls.includes('wf-col-6')) colSpan = 6
    else if (cls.includes('wf-col-4')) colSpan = 4
    else if (cls.includes('wf-col-3')) colSpan = 3
    else if (cls.includes('wf-col-8')) colSpan = 8
    else if (cls.includes('wf-col-12')) colSpan = 12

    const colWidth = (ctx.maxWidth - gap * 11) / 12 * colSpan + gap * (colSpan - 1)

    // Wrap to next row if needed
    if (cursorX + colWidth > ctx.maxWidth + 1) {
      cursorX = 0
      cursorY += rowMaxHeight + gap
      rowMaxHeight = 0
    }

    // Walk children from y=0 (relative to cell), then position the cell frame at cursorY
    const cellChildren = walkChildren(child, { x: 0, y: 0, maxWidth: colWidth })
    const cellBounds = getBounds(cellChildren)
    const cellHeight = cellBounds.height || 60

    if (cellChildren.length > 0) {
      children.push({
        id: nextId(), type: 'frame',
        x: cursorX, y: cursorY, width: colWidth, height: cellHeight,
        children: cellChildren,
      })
    }

    rowMaxHeight = Math.max(rowMaxHeight, cellHeight)
    cursorX += colWidth + gap
  }

  const totalHeight = cursorY + rowMaxHeight

  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y, width: ctx.maxWidth, height: totalHeight,
    label: 'Grid', children,
  }
}

function convertActions(el: Element, ctx: Ctx): WireframeElement | null {
  // wf-actions is always display:flex from CSS — treat as horizontal button row
  const children: WireframeElement[] = []
  let cursorX = 0
  const gap = 8

  for (const child of Array.from(el.children)) {
    const converted = convertElement(child, { x: cursorX, y: 0, maxWidth: 200 })
    if (converted) {
      converted.x = cursorX
      converted.y = 0
      children.push(converted)
      cursorX += converted.width + gap
    }
  }

  if (children.length === 0) return null

  const bounds = getBounds(children)
  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y,
    width: Math.max(bounds.width, cursorX), height: bounds.height || 32,
    label: 'Actions', children,
  }
}

function convertFlexRow(el: Element, ctx: Ctx, _style: Record<string, string>): WireframeElement | null {
  const children: WireframeElement[] = []
  let cursorX = 0
  const gap = 12

  for (const child of Array.from(el.children)) {
    const childStyle = parseInlineStyle((child as HTMLElement).style?.cssText || child.getAttribute('style') || '')
    const childWidth = parsePixels(childStyle.width) || parsePixels(childStyle['min-width']) || 200
    const converted = convertElement(child, { x: cursorX, y: 0, maxWidth: childWidth })
    if (converted) {
      converted.x = cursorX
      converted.y = 0
      children.push(converted)
      cursorX += converted.width + gap
    }
  }

  if (children.length === 0) return null

  const bounds = getBounds(children)
  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y,
    width: Math.max(bounds.width, ctx.maxWidth), height: bounds.height,
    label: 'Row', children,
  }
}

function convertPagination(el: Element, ctx: Ctx): WireframeElement {
  const children: WireframeElement[] = []
  let cursorX = 0
  const gap = 8

  // Flatten: pagination might have nested divs (wf-actions inside)
  const allChildren = el.querySelectorAll('.wf-btn, .wf-actions > .wf-btn')
  const directTexts: Element[] = []

  for (const child of Array.from(el.children)) {
    const cls = child.className?.toString?.() || ''
    if (cls.includes('wf-btn')) {
      // handled below
    } else if (cls.includes('wf-actions')) {
      // skip wrapper, buttons handled via querySelectorAll
    } else {
      directTexts.push(child)
    }
  }

  // Add text elements first
  for (const textEl of directTexts) {
    const text = textEl.textContent?.trim() || ''
    if (!text) continue
    const w = Math.max(60, text.length * 8 + 16)
    children.push({
      id: nextId(), type: 'text',
      x: cursorX, y: 6, width: w, height: 20,
      label: text, fontSize: 12, fillColor: '#8c8c8c',
    })
    cursorX += w + gap
  }

  // Add buttons
  const seenBtns = new Set<Element>()
  for (const btn of Array.from(allChildren)) {
    if (seenBtns.has(btn)) continue
    seenBtns.add(btn)
    const text = btn.textContent?.trim() || ''
    if (!text) continue
    children.push({
      id: nextId(), type: 'button',
      x: cursorX, y: 0, width: 60, height: 32,
      label: text, fillColor: '#f5f5f5', cornerRadius: 4, fontSize: 14,
    })
    cursorX += 60 + gap
  }

  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y, width: Math.max(cursorX, 200), height: 32,
    label: 'Pagination', children,
  }
}

function convertButton(el: Element, ctx: Ctx, defaultColor: string): WireframeElement {
  const label = el.textContent?.trim() || 'Button'
  const w = Math.max(80, label.length * 10 + 32)
  const isPrimary = el.className?.includes?.('wf-btn--primary')

  return {
    id: nextId(), type: 'button',
    x: ctx.x, y: ctx.y, width: w, height: 32,
    label,
    fillColor: isPrimary ? '#1890ff' : defaultColor,
    cornerRadius: 4, fontSize: 14,
  }
}

function convertCheckbox(el: Element, ctx: Ctx): WireframeElement {
  const isRadio = el.getAttribute('type') === 'radio'
  const size = 16
  return {
    id: nextId(),
    type: 'frame',
    x: ctx.x, y: ctx.y,
    width: size, height: size,
    fillColor: '#FFFFFF',
    strokeColor: '#d9d9d9',
    strokeWidth: 1,
    cornerRadius: isRadio ? 8 : 3,
    label: isRadio ? 'Radio' : 'Checkbox',
  }
}

function convertInput(el: Element, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const placeholder = el.getAttribute('placeholder') || el.getAttribute('aria-label') || 'Input'
  const w = parsePixels(style.width) || 200
  const type = el.getAttribute('type')
  const isTextarea = el.tagName === 'TEXTAREA'
  const rows = parseInt(el.getAttribute('rows') || '1', 10)
  const h = isTextarea ? Math.max(36, rows * 20 + 16) : 36

  return {
    id: nextId(), type: 'input',
    x: ctx.x, y: ctx.y, width: w, height: h,
    label: type === 'date' ? 'YYYY-MM-DD' : placeholder,
    cornerRadius: 4, fontSize: 14,
  }
}

function convertChip(el: Element, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const label = el.textContent?.trim() || 'Chip'
  return {
    id: nextId(), type: 'button',
    x: ctx.x, y: ctx.y,
    width: Math.max(80, label.length * 9 + 20), height: 24,
    label,
    fillColor: style['background'] || '#e6f7ff',
    cornerRadius: 12, fontSize: 13,
  }
}

function convertBadge(el: Element, ctx: Ctx, _style: Record<string, string>): WireframeElement {
  const label = el.textContent?.trim() || ''
  return {
    id: nextId(), type: 'button',
    x: ctx.x, y: ctx.y,
    width: Math.max(40, label.length * 9 + 16), height: 24,
    label,
    fillColor: '#f0f0f0', cornerRadius: 12, fontSize: 12,
  }
}

function convertState(el: Element, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const text = el.textContent?.trim() || 'State placeholder'
  const isError = el.className?.includes?.('wf-state--error')
  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y,
    width: ctx.maxWidth, height: 40,
    fillColor: '#fafafa',
    strokeColor: isError ? '#ff4d4f' : '#d9d9d9',
    strokeWidth: 1, cornerRadius: 8,
    label: text,
    children: [{
      id: nextId(), type: 'text',
      x: 12, y: 10, width: ctx.maxWidth - 24, height: 20,
      label: text, fontSize: 12, fillColor: isError ? '#ff4d4f' : '#8c8c8c',
    }],
  }
}

function convertEmpty(el: Element, ctx: Ctx, _style: Record<string, string>): WireframeElement {
  const children: WireframeElement[] = []
  let innerY = 14

  const titleEl = el.querySelector('.wf-empty__title')
  if (titleEl) {
    const title = titleEl.textContent?.trim() || ''
    children.push({
      id: nextId(), type: 'text',
      x: 14, y: innerY, width: ctx.maxWidth - 28, height: 20,
      label: title, fontSize: 14, fillColor: '#000000',
    })
    innerY += 28
  }

  const descEl = el.querySelector('.wf-empty__desc')
  if (descEl) {
    const desc = descEl.textContent?.trim() || ''
    children.push({
      id: nextId(), type: 'text',
      x: 14, y: innerY, width: ctx.maxWidth - 28, height: 16,
      label: desc, fontSize: 12, fillColor: '#8c8c8c',
    })
    innerY += 24
  }

  // Actions inside empty state
  const actionsEl = el.querySelector('.wf-actions')
  if (actionsEl) {
    let btnX = 14
    for (const btn of Array.from(actionsEl.querySelectorAll('.wf-btn'))) {
      const label = btn.textContent?.trim() || ''
      const w = Math.max(80, label.length * 10 + 32)
      const isPrimary = btn.className.includes('wf-btn--primary')
      children.push({
        id: nextId(), type: 'button',
        x: btnX, y: innerY, width: w, height: 32,
        label, fillColor: isPrimary ? '#1890ff' : '#f5f5f5',
        cornerRadius: 4, fontSize: 14,
      })
      btnX += w + 8
    }
    innerY += 40
  }

  // Fallback: if no structured children, just get text
  if (children.length === 0) {
    const text = el.textContent?.trim() || 'No data'
    children.push({
      id: nextId(), type: 'text',
      x: 14, y: 14, width: ctx.maxWidth - 28, height: 20,
      label: text, fontSize: 14, fillColor: '#bfbfbf',
    })
    innerY = 48
  }

  return {
    id: nextId(), type: 'frame',
    x: ctx.x, y: ctx.y,
    width: ctx.maxWidth, height: innerY + 14,
    fillColor: '#fafafa', strokeColor: '#e8e8e8', strokeWidth: 1,
    cornerRadius: 8, label: 'Empty State',
    children,
  }
}

function convertLabel(el: Element, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const text = el.textContent?.trim() || ''
  return {
    id: nextId(), type: 'text',
    x: ctx.x, y: ctx.y,
    width: Math.min(ctx.maxWidth, Math.max(60, text.length * 8 + 8)),
    height: 18,
    label: text, fontSize: 12,
    fillColor: style.color || '#595959',
  }
}

function convertText(el: Element, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const text = el.textContent?.trim() || ''
  const fontSize = parsePixels(style['font-size']) || 16
  return {
    id: nextId(), type: 'text',
    x: ctx.x, y: ctx.y,
    width: Math.min(ctx.maxWidth, Math.max(100, text.length * fontSize * 0.6)),
    height: fontSize + 8,
    label: text, fontSize,
    fillColor: style.color || '#000000',
  }
}

function makeText(text: string, ctx: Ctx, style: Record<string, string>): WireframeElement {
  const fontSize = parsePixels(style['font-size']) || 14
  return {
    id: nextId(), type: 'text',
    x: ctx.x, y: ctx.y,
    width: Math.min(ctx.maxWidth, Math.max(60, text.length * fontSize * 0.6)),
    height: fontSize + 8,
    label: text, fontSize,
    fillColor: style.color || '#000000',
  }
}

// ── Helpers ──

function parseInlineStyle(cssText: string): Record<string, string> {
  const result: Record<string, string> = {}
  if (!cssText) return result
  for (const decl of cssText.split(';')) {
    const colon = decl.indexOf(':')
    if (colon < 0) continue
    const prop = decl.slice(0, colon).trim()
    const val = decl.slice(colon + 1).trim()
    if (prop && val) result[prop] = val
  }
  return result
}

function parsePixels(value: string | undefined): number {
  if (!value) return 0
  const m = value.match(/([\d.]+)px/)
  return m ? parseFloat(m[1]) : 0
}

function getDirectText(el: Element): string {
  let text = ''
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType === 3) text += node.textContent || ''
  }
  return text
}

function getBounds(elements: WireframeElement[]): { width: number; height: number; bottom: number } {
  if (elements.length === 0) return { width: 0, height: 0, bottom: 0 }
  let maxRight = 0
  let maxBottom = 0
  for (const el of elements) {
    maxRight = Math.max(maxRight, el.x + el.width)
    maxBottom = Math.max(maxBottom, el.y + el.height)
  }
  return { width: maxRight, height: maxBottom, bottom: maxBottom }
}
