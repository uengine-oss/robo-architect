/**
 * Log-Driven Vibe Coding (LDVC) logger
 *
 * Goals:
 * - Narrative logs humans can read
 * - Structured context machines can parse
 * - Safe defaults (no huge payloads, DEV=debug, PROD=info)
 *
 * Usage:
 *   import { createLogger, newOpId } from '@/app/logging/logger'
 *   const log = createLogger({ scope: 'App' })
 *   log.info('app_mounted', 'App mounted successfully.', { appInstanceId })
 */

const LEVEL = /** @type {const} */ ({
  debug: 10,
  info: 20,
  warn: 30,
  error: 40
})

function readEnv() {
  // Vite provides import.meta.env; keep this safe in non-Vite runtimes.
  try {
    // eslint-disable-next-line no-undef
    return (import.meta && import.meta.env) ? import.meta.env : {}
  } catch {
    return {}
  }
}

function resolveMinLevel() {
  const env = readEnv()
  const defaultLevel = env.DEV ? 'debug' : 'info'
  const override = (globalThis && globalThis.__LDVC_LOG_LEVEL__) || defaultLevel
  return LEVEL[override] ?? LEVEL.info
}

function nowIso() {
  return new Date().toISOString()
}

export function newOpId(prefix = 'op') {
  // Short, human-readable, low collision for local debugging.
  const rand = Math.random().toString(36).slice(2, 8)
  const time = Date.now().toString(36).slice(-4)
  return `${prefix}_${rand}${time}`
}

function safeJson(value, maxLen = 800) {
  try {
    const s = JSON.stringify(value)
    if (typeof s === 'string' && s.length > maxLen) return `${s.slice(0, maxLen)}…`
    return s
  } catch (e) {
    return `"[[unserializable:${e?.message || 'unknown'}]]"`
  }
}

function kvString(ctx) {
  if (!ctx || typeof ctx !== 'object') return ''
  const parts = []
  for (const [k, v] of Object.entries(ctx)) {
    if (v === undefined) continue
    if (v === null) {
      parts.push(`${k}=null`)
      continue
    }
    const t = typeof v
    if (t === 'string' || t === 'number' || t === 'boolean') {
      const vs = String(v)
      parts.push(`${k}=${vs.length > 120 ? `${vs.slice(0, 120)}…` : vs}`)
      continue
    }
    // Objects/arrays: keep it compact in the message, preserve full structure in the payload.
    parts.push(`${k}=${safeJson(v, 200)}`)
  }
  return parts.length ? ` | ${parts.join(' ')}` : ''
}

function toConsoleFn(level) {
  if (level === 'debug') return console.debug ? console.debug.bind(console) : console.log.bind(console)
  if (level === 'info') return console.info ? console.info.bind(console) : console.log.bind(console)
  if (level === 'warn') return console.warn.bind(console)
  return console.error.bind(console)
}

export function createLogger({ scope }) {
  const minLevel = resolveMinLevel()

  /** @param {'debug'|'info'|'warn'|'error'} level */
  function shouldLog(level) {
    return (LEVEL[level] ?? LEVEL.info) >= minLevel
  }

  /**
   * @param {'debug'|'info'|'warn'|'error'} level
   * @param {string} event
   * @param {string} message
   * @param {object} [context]
   */
  function emit(level, event, message, context = {}) {
    if (!shouldLog(level)) return

    const payload = {
      ts: nowIso(),
      level,
      scope,
      event,
      message,
      ...context
    }

    const line = `[LDVC][${level.toUpperCase()}][${scope}] ${message}${kvString({ event, ...context })}`
    toConsoleFn(level)(line, payload)
  }

  return {
    debug: (event, message, context) => emit('debug', event, message, context),
    info: (event, message, context) => emit('info', event, message, context),
    warn: (event, message, context) => emit('warn', event, message, context),
    error: (event, message, context) => emit('error', event, message, context)
  }
}


