import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'app_language'
const TAG_PATTERN = /^[A-Za-z0-9-]+$/
const MIN_TAG_LENGTH = 2
const MAX_TAG_LENGTH = 35

function validateTag(tag) {
  if (typeof tag !== 'string') return false
  if (tag.length < MIN_TAG_LENGTH || tag.length > MAX_TAG_LENGTH) return false
  return TAG_PATTERN.test(tag)
}

// Read a persisted value if present and valid; otherwise return null.
// Validation runs against arbitrary localStorage contents (a user could have
// pasted garbage in devtools), so reject and let the caller fall through.
function readPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw && validateTag(raw)) return raw
  } catch {
    // localStorage may be disabled (private windows, strict browser settings);
    // silently fall through to navigator-locale default.
  }
  return null
}

function browserLocaleDefault() {
  // navigator.language is BCP-47 in every modern browser; defensive fallback
  // for non-browser test environments where it may be undefined.
  return (typeof navigator !== 'undefined' && navigator.language) || 'en-US'
}

export const useLanguageStore = defineStore('language', () => {
  // Effective output language for AI-generated content (feature 031).
  // BCP-47 tag (e.g. "ko-KR", "en-US"). Read by the global window.fetch
  // patch installed at bootstrap and sent as Accept-Language on every
  // outbound API request.
  const language = ref(browserLocaleDefault())

  // Lazy persistence: do NOT write to localStorage at init. A user who never
  // touches the Settings panel should keep tracking their browser locale
  // across sessions even if that locale changes. Only an explicit setLanguage
  // call (from the Settings UI) creates the persisted entry — see spec US1/US2.
  function initLanguage() {
    const persisted = readPersisted()
    if (persisted) {
      language.value = persisted
    } else {
      language.value = browserLocaleDefault()
    }
  }

  function setLanguage(tag) {
    if (!validateTag(tag)) {
      // eslint-disable-next-line no-console
      console.warn(
        `[language.store] Rejected invalid language tag "${tag}". ` +
          `Expected a BCP-47-like string (2–35 chars, [A-Za-z0-9-]). ` +
          `Current value (${language.value}) unchanged.`,
      )
      return
    }
    language.value = tag
    try {
      localStorage.setItem(STORAGE_KEY, tag)
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn(
        `[language.store] Failed to persist language to localStorage (${e?.message || e}). ` +
          `Setting will not survive page reload.`,
      )
    }
  }

  // Eager init on store creation. This means `useLanguageStore()` always
  // returns a populated store even if called before main.js explicitly calls
  // initLanguage(). The explicit call in main.js is still useful for
  // re-initialization in tests.
  initLanguage()

  return {
    language,
    initLanguage,
    setLanguage,
  }
})
