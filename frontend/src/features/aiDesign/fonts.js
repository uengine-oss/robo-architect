/**
 * Korean font preload for the open-pencil FrameEditor canvas.
 *
 * Why we need this:
 * open-pencil's CanvasKit renderer keeps its own typeface registry. To draw
 * Korean glyphs it needs `ensureCJKFallback()` to register a CJK font into
 * that registry. The default fallback chain is:
 *   1. `window.queryLocalFonts()` — needs a user gesture, denied on first paint.
 *   2. Google Fonts metadata API — the bundled API key is rate-limited (429),
 *      so it can't discover the woff2 URL even though gstatic itself is up.
 * When both fail we get tofu (□□□) for any Hangul.
 *
 * Fix: serve a Korean TTF/OTF from `/Pretendard-Regular.otf` (placed in
 * `public/`) and register it via `markFontLoaded` + `setCJKFallbackFamily`
 * before any FrameEditor mounts. open-pencil caches the buffer in its
 * module-level `loadedFamilies` map; when a renderer's `initFontService()`
 * runs later, it replays the cache into the new TypefaceFontProvider, so the
 * font is always available no matter when the editor is created.
 */

import { markFontLoaded, setCJKFallbackFamily } from '@open-pencil/core'

const KOREAN_FONT_FAMILY = 'Pretendard'
const KOREAN_FONT_URL = '/Pretendard-Regular.otf'

let loadingPromise = null

export function preloadKoreanFont() {
  if (loadingPromise) return loadingPromise
  loadingPromise = (async () => {
    try {
      const res = await fetch(KOREAN_FONT_URL)
      if (!res.ok) {
        console.warn(`[fonts] Korean font fetch failed: ${res.status}`)
        return
      }
      const buffer = await res.arrayBuffer()
      // Cache in open-pencil's font registry. When a FrameEditor's
      // SkiaRenderer later calls initFontService(), it re-registers every
      // entry in this cache into the fresh TypefaceFontProvider.
      markFontLoaded(KOREAN_FONT_FAMILY, 'Regular', buffer)
      // Promote it to CJK fallback so glyphs missing from Inter (Hangul, etc.)
      // route to Pretendard instead of triggering the network-dependent
      // ensureCJKFallback() probe chain.
      setCJKFallbackFamily(KOREAN_FONT_FAMILY)
    } catch (err) {
      console.warn('[fonts] Korean font preload failed:', err)
    }
  })()
  return loadingPromise
}
