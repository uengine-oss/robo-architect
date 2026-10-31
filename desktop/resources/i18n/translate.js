// English mode: Korean → English through one dictionary (ko-en.json) for the shell, Studio, the
// portal, code apps and the main process's menus. The app's screens hardcode Korean; instead of
// rewriting every component, this translates what reaches the screen — text nodes, placeholder /
// title / aria-label, alert/confirm, canvas text (charts measure and draw the same English), and
// Korean date/number formats — and keeps doing so as the page changes. In Korean mode it does nothing.
//   browser: window.OS_LANG ('ko' | 'en') and window.__osDict before this script; osI18n.missing()
//            lists the Korean it could not translate (the English capture runs read it)
//   node:    require('…/translate.js').create(dict).tr(text)
;(function (root) {
  'use strict'
  const HANGUL = /[가-힣]/

  function create(dict) {
    const exact = (dict && dict.exact) || {}
    // where the same Korean means something else: [css selector, Korean, English]
    const context = (dict && dict.context) || []
    const pats = ((dict && dict.patterns) || []).map(([ko, en]) => {
      const parts = ko.split(/\{(\d+)\}/)
      let re = '^'
      const order = []
      parts.forEach((p, i) => {
        if (i % 2) { re += '([\\s\\S]+?)'; order.push(Number(p)) } else re += p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      })
      return { re: new RegExp(re + '$'), order, en, lit: ko.replace(/\{\d+\}/g, '').length }
    }).sort((a, b) => b.lit - a.lit)
    const cache = new Map()
    const missing = new Set()

    // Korean number units (chart axes: "10.0만", "1.2억") → English compact numbers ("100K", "120M")
    const UNIT = { '만': 1e4, '억': 1e8 }
    const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
    function core(s) {
      if (Object.prototype.hasOwnProperty.call(exact, s)) return exact[s]
      const u = s.match(/^(-?\d+(?:\.\d+)?)\s?(만|억)$/)
      if (u) return compact.format(Number(u[1]) * UNIT[u[2]])
      for (const p of pats) {
        const m = s.match(p.re)
        if (!m) continue
        const vals = {}
        p.order.forEach((n, i) => { vals[n] = tr(m[i + 1]) })
        return p.en.replace(/\{(\d+)\}/g, (_, n) => (vals[n] == null ? '' : vals[n]))
      }
      return undefined
    }
    /** Translated text, keeping the surrounding whitespace; the input itself when there is no entry. */
    function tr(s) {
      if (typeof s !== 'string' || !HANGUL.test(s)) return s
      if (cache.has(s)) return cache.get(s)
      const [, lead, body, tail] = s.match(/^(\s*)([\s\S]*?)(\s*)$/)
      let out = core(body)
      if (out === undefined) {
        // an icon or mark glued to a known string: "▤ 자원 닫기", "✓ 완료"
        const m = body.match(/^([^\p{L}\p{N}]*)([\s\S]*?\p{L}[\s\S]*?)([^\p{L}\p{N}]*)$/u)
        if (m && (m[1] || m[3])) { const t = core(m[2]); if (t !== undefined) out = m[1] + t + m[3] }
      }
      if (out === undefined && body.includes('\n')) {
        const lines = body.split('\n').map((l) => tr(l))
        if (lines.some((l, i) => l !== body.split('\n')[i])) out = lines.join('\n')
      }
      if (out === undefined) { missing.add(body); out = body }
      out = lead + out + tail
      cache.set(s, out)
      return out
    }
    /** Only what the dictionary has word for word — for inline <code>, which may hold real code. */
    const exactOnly = (s) => {
      const [, lead, body, tail] = s.match(/^(\s*)([\s\S]*?)(\s*)$/)
      return Object.prototype.hasOwnProperty.call(exact, body) ? lead + exact[body] + tail : s
    }
    /** The context entry for this text inside `el`, if one applies. */
    const inContext = (el, s) => {
      const body = s.trim()
      for (const [sel, ko, en] of context) if (ko === body && el.closest(sel)) return s.replace(body, en)
      return undefined
    }
    return { tr, exactOnly, inContext, missing: () => [...missing] }
  }

  function install(win, t) {
    const doc = win.document
    const ATTRS = ['placeholder', 'data-placeholder', 'title', 'aria-label', 'alt', 'label', 'data-tooltip']
    const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'PRE', 'NOSCRIPT'])
    const userText = (el) => el && (SKIP.has(el.tagName) || el.isContentEditable || !!el.closest('pre'))
    function text(node) {
      const v = node.nodeValue
      if (!HANGUL.test(v) || userText(node.parentElement)) return
      // inline <code> may be real code: only what the dictionary has word for word
      const el = node.parentElement
      const out = (el && t.inContext(el, v)) || (el && el.closest('code') ? t.exactOnly(v) : t.tr(v))
      if (out !== v) node.nodeValue = out
    }
    function attrs(el) {
      for (const a of ATTRS) {
        const v = el.getAttribute(a)
        if (v && HANGUL.test(v)) { const out = t.tr(v); if (out !== v) el.setAttribute(a, out) }
      }
      if (el.tagName === 'INPUT' && /^(button|submit|reset)$/.test(el.type) && HANGUL.test(el.value)) el.value = t.tr(el.value)
    }
    function walk(node) {
      if (node.nodeType === 3) return text(node)
      if (node.nodeType !== 1 && node.nodeType !== 11) return
      if (node.nodeType === 1) {
        attrs(node)
        if (userText(node)) return
        if (node.shadowRoot) { walk(node.shadowRoot); observe(node.shadowRoot) }
      }
      for (let c = node.firstChild; c; c = c.nextSibling) walk(c)
    }
    function observe(target) {
      new win.MutationObserver((list) => {
        for (const m of list) {
          if (m.type === 'characterData') text(m.target)
          else if (m.type === 'attributes') attrs(m.target)
          else m.addedNodes.forEach(walk)
        }
      }).observe(target, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS })
    }
    // dialogs
    for (const fn of ['alert', 'confirm', 'prompt']) {
      const orig = win[fn]
      if (orig) win[fn] = function (msg, ...rest) { return orig.call(win, t.tr(msg), ...rest) }
    }
    // canvas text (ECharts, Cytoscape): measure and draw the same translated string
    for (const C of [win.CanvasRenderingContext2D, win.OffscreenCanvasRenderingContext2D]) {
      if (!C) continue
      for (const m of ['fillText', 'strokeText', 'measureText']) {
        const orig = C.prototype[m]
        C.prototype[m] = function (s, ...rest) { return orig.call(this, t.tr(s), ...rest) }
      }
    }
    // dates and numbers: Korean (or unspecified) locale → en-US
    const en = (l) => (l == null || (typeof l === 'string' && /^ko\b/i.test(l)) || (Array.isArray(l) && l.some((x) => /^ko\b/i.test(x))) ? 'en-US' : l)
    for (const [C, ms] of [[win.Date, ['toLocaleString', 'toLocaleDateString', 'toLocaleTimeString']], [win.Number, ['toLocaleString']]]) {
      for (const m of ms) { const orig = C.prototype[m]; C.prototype[m] = function (l, o) { return orig.call(this, en(l), o) } }
    }
    for (const name of ['DateTimeFormat', 'NumberFormat', 'RelativeTimeFormat', 'PluralRules', 'ListFormat']) {
      const Orig = win.Intl[name]
      if (!Orig) continue
      const Wrapped = function (l, o) { return new Orig(en(l), o) }
      Wrapped.prototype = Orig.prototype
      Wrapped.supportedLocalesOf = Orig.supportedLocalesOf
      win.Intl[name] = Wrapped
    }
    doc.documentElement.lang = 'en'
    const start = () => { walk(doc.documentElement); observe(doc.documentElement) }
    if (doc.documentElement) start()
  }

  const api = { create, install }
  if (typeof module !== 'undefined' && module.exports) module.exports = api
  else {
    const t = create(root.__osDict)
    root.osI18n = { lang: root.OS_LANG || 'ko', tr: root.OS_LANG === 'en' ? t.tr : (s) => s, missing: t.missing }
    if (root.OS_LANG === 'en') install(root, t)
  }
})(typeof window !== 'undefined' ? window : globalThis)
