import { computed } from 'vue'
import { useLanguageStore } from './language.store'
import { messages } from './messages'

// Lightweight, dependency-free i18n helper (no vue-i18n).
//
// The app already tracks an effective output language in language.store.js
// (a BCP-47 tag like "ko-KR" / "en-US", used as Accept-Language for AI
// generation). We reuse that single source of truth for UI labels too:
// reduce the tag to its base language ("ko-KR" → "ko") and look the key up
// in the messages dictionary. Any non-Korean base falls back to English so
// the UI is bilingual today and extensible to more locales later.
//
// Usage in a component:
//   const { t } = useI18n()
//   ...
//   {{ t('proposal.strategicDesign') }}
//   {{ t('proposal.streamLines', { n: 3 }) }}  // "{n}" interpolation

const DEFAULT_LANG = 'en'

function baseLang(tag) {
  return String(tag || DEFAULT_LANG)
    .split('-')[0]
    .toLowerCase()
}

// Resolve a single key against the dictionary for the given base language,
// with an English fallback and a Korean fallback (so a half-translated entry
// still renders something). Unknown keys return the key itself, which makes
// missing translations visible during development rather than blank.
function resolve(key, lang) {
  const entry = messages[key]
  if (!entry) return key
  return entry[lang] ?? entry[DEFAULT_LANG] ?? entry.ko ?? key
}

function interpolate(str, vars) {
  if (!vars) return str
  return String(str).replace(/\{(\w+)\}/g, (m, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : m,
  )
}

// Reactive composable. The returned `t` is recomputed whenever the language
// store changes, so switching locale in Settings re-renders all labels.
export function useI18n() {
  const lang = useLanguageStore()
  const base = computed(() => baseLang(lang.language))
  function t(key, vars) {
    return interpolate(resolve(key, base.value), vars)
  }
  return { t, lang: base }
}

// Non-reactive one-shot lookup for places without a component instance
// (store actions, plain modules). Reads the language store synchronously.
export function translate(key, vars) {
  const lang = useLanguageStore()
  return interpolate(resolve(key, baseLang(lang.language)), vars)
}
