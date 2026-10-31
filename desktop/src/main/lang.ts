/**
 * UI language, "ko" or "en", chosen once per start (the same scheme as Ontological Studio's
 * desktop, its src/main/lang.js):
 *
 *   ROBO_LANG (recordings, tests force it) > --lang=<ko|en> on the command line
 *   > <userData>/language.json { language } (menu 언어 / Language) > the OS language
 *   (Korean → "ko", anything else → "en").
 *
 * English mode does not rewrite the screens. Every page the app serves (shell/home, every tab,
 * the analyzer remote inside the Legacy tab) gets window.OS_LANG, the dictionary and
 * resources/i18n/translate.js in its <head>; the translator turns the Korean that reaches the
 * screen into English through resources/i18n/ko-en.json. The main process uses the same
 * dictionary for its menus (tr()). In Korean mode nothing is injected and tr() is the identity.
 *
 * The Chromium locale (--lang) follows the choice too, so navigator.language — which the SPA's
 * messages.js and its Accept-Language header read — agrees with the rest of the screen.
 */

import { app } from "electron";
import fs from "node:fs";
import path from "node:path";

export type Lang = "ko" | "en";

interface Translator {
  tr: (s: string) => string;
}

let lang: Lang = "ko";
let source = "default";
let t: Translator = { tr: (s) => s };

/** desktop/resources/i18n in development, <resources>/i18n in a package. */
export function i18nDir(): string {
  const dev = path.resolve(app.getAppPath(), "resources", "i18n");
  if (fs.existsSync(dev)) return dev;
  return path.join(process.resourcesPath, "i18n");
}

function savedFile(): string {
  return path.join(app.getPath("userData"), "language.json");
}

const pick = (v: unknown): Lang | null => {
  const s = String(v ?? "").trim().toLowerCase();
  if (s === "ko" || s.startsWith("ko-") || s.startsWith("ko_")) return "ko";
  if (s === "en" || s.startsWith("en-") || s.startsWith("en_")) return "en";
  return null;
};

function readSaved(): Lang | null {
  try {
    return pick((JSON.parse(fs.readFileSync(savedFile(), "utf8")) as { language?: string }).language);
  } catch {
    return null;
  }
}

function osLanguage(): Lang {
  let tag = "";
  try {
    tag = (app.getPreferredSystemLanguages?.() || [])[0] || "";
  } catch {
    /* not available on this platform */
  }
  if (!tag) tag = process.env.LC_ALL || process.env.LANG || "";
  return String(tag).toLowerCase().startsWith("ko") ? "ko" : "en";
}

/**
 * Decide the language. Must run before app "ready" — it sets Chromium's --lang so every
 * renderer's navigator.language matches.
 */
export function initLanguage(): Lang {
  const env = pick(process.env.ROBO_LANG);
  const cli = pick(app.commandLine.getSwitchValue("lang"));
  const saved = readSaved();
  if (env) [lang, source] = [env, "ROBO_LANG"];
  else if (cli) [lang, source] = [cli, "--lang"];
  else if (saved) [lang, source] = [saved, "saved"];
  else [lang, source] = [osLanguage(), "os"];
  app.commandLine.appendSwitch("lang", lang === "en" ? "en-US" : "ko");
  if (lang === "en") {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- a plain script shared with the renderer
      const mod = require(path.join(i18nDir(), "translate.js")) as { create: (d: unknown) => Translator };
      t = mod.create(JSON.parse(fs.readFileSync(path.join(i18nDir(), "ko-en.json"), "utf8")));
    } catch (err) {
      console.error("lang.dictionary_failed", err);
    }
  }
  return lang;
}

export const currentLang = (): Lang => lang;
export const langSource = (): string => source;

/** Korean UI text → the current language (menus, dialogs, tab titles of the main process). */
export const tr = (s: string): string => (lang === "en" ? t.tr(s) : s);

/** The menu choice; takes effect at the next start (the menu restarts the app). */
export function saveLanguage(next: Lang): void {
  fs.mkdirSync(path.dirname(savedFile()), { recursive: true });
  fs.writeFileSync(savedFile(), JSON.stringify({ language: next }, null, 2) + "\n");
}

/** An HTML page of ours with English mode switched on; Korean mode returns it unchanged. */
export function injectHtml(html: string): string {
  if (lang !== "en") return html;
  const tags =
    '<script>window.OS_LANG="en"</script>' +
    '<script src="/__i18n/dict.js"></script>' +
    '<script src="/__i18n/translate.js"></script>' +
    '<link rel="stylesheet" href="/__i18n/en.css">';
  return /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + tags) : tags + html;
}

/**
 * /__i18n/translate.js, /__i18n/dict.js (the dictionary as a script) and /__i18n/en.css (layout
 * fixes for longer English text); null for other paths.
 */
export function i18nAsset(pathname: string): { type: string; body: string } | null {
  const js = "text/javascript; charset=utf-8";
  if (pathname === "/__i18n/en.css") return { type: "text/css; charset=utf-8", body: fs.readFileSync(path.join(i18nDir(), "en.css"), "utf8") };
  if (pathname === "/__i18n/translate.js") return { type: js, body: fs.readFileSync(path.join(i18nDir(), "translate.js"), "utf8") };
  if (pathname === "/__i18n/dict.js") {
    const dict = lang === "en" ? fs.readFileSync(path.join(i18nDir(), "ko-en.json"), "utf8") : "{}";
    return { type: js, body: `window.__osDict=${dict}` };
  }
  return null;
}
