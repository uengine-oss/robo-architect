from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from typing import Literal, Tuple

WireframeTheme = Literal["ant", "material"]

MAX_TEMPLATE_LEN = 50_000


@dataclass
class NormalizeReport:
    # Size
    len_before: int = 0
    len_after: int = 0

    # Corrections applied
    stripped_markdown_fences: bool = False
    removed_doc_root: bool = False
    removed_script: bool = False
    removed_inline_handlers: bool = False
    removed_js_urls: bool = False
    removed_link_tags: bool = False

    # Style policy
    style_found: bool = False
    style_dropped_unscoped: bool = False
    style_dropped_import_or_url: bool = False
    style_sanitized_fixed_removed: bool = False
    style_sanitized_z_index_clamped: bool = False

    # Wrapping/theme
    added_root_wrapper: bool = False
    root_already_present: bool = False
    ensured_root_attrs: bool = False
    theme_selected: WireframeTheme = "ant"

    # Recovery
    fallback_used: bool = False
    size_truncated_by_dropping_style: bool = False

    def as_dict(self) -> dict:
        return {
            "len_before": self.len_before,
            "len_after": self.len_after,
            "stripped_markdown_fences": self.stripped_markdown_fences,
            "removed_doc_root": self.removed_doc_root,
            "removed_script": self.removed_script,
            "removed_inline_handlers": self.removed_inline_handlers,
            "removed_js_urls": self.removed_js_urls,
            "removed_link_tags": self.removed_link_tags,
            "style_found": self.style_found,
            "style_dropped_unscoped": self.style_dropped_unscoped,
            "style_dropped_import_or_url": self.style_dropped_import_or_url,
            "style_sanitized_fixed_removed": self.style_sanitized_fixed_removed,
            "style_sanitized_z_index_clamped": self.style_sanitized_z_index_clamped,
            "added_root_wrapper": self.added_root_wrapper,
            "root_already_present": self.root_already_present,
            "ensured_root_attrs": self.ensured_root_attrs,
            "theme_selected": self.theme_selected,
            "fallback_used": self.fallback_used,
            "size_truncated_by_dropping_style": self.size_truncated_by_dropping_style,
        }


def strip_markdown_fences(text: str) -> tuple[str, bool]:
    """
    Best-effort removal of markdown code fences the LLM might accidentally emit.
    """
    s = (text or "").strip()
    if not s:
        return "", False
    before = s
    # Remove leading ```lang and trailing ```
    s = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    s = s.strip()
    return s, (s != before)


def _select_theme(*, theme_hint: str | None, html_text: str | None) -> WireframeTheme:
    hint = f"{theme_hint or ''}\n{html_text or ''}".lower()
    if any(k in hint for k in ["material", "mui", "material design", "md3", "google"]):
        return "material"
    if any(k in hint for k in ["ant", "antd", "ant design"]):
        return "ant"
    # default
    return "ant"


def _remove_document_root(html: str) -> tuple[str, bool]:
    if not html:
        return "", False
    before = html
    # doctype
    html = re.sub(r"(?is)<!doctype[^>]*>", "", html)
    # remove <head> entirely
    html = re.sub(r"(?is)<\s*head\b[^>]*>.*?<\s*/\s*head\s*>", "", html)
    # unwrap html/body tags (keep inner content)
    html = re.sub(r"(?is)<\s*/\s*html\s*>", "", html)
    html = re.sub(r"(?is)<\s*html\b[^>]*>", "", html)
    html = re.sub(r"(?is)<\s*/\s*body\s*>", "", html)
    html = re.sub(r"(?is)<\s*body\b[^>]*>", "", html)
    return html.strip(), (html.strip() != before.strip())


def _sanitize_baseline(html: str, report: NormalizeReport) -> str:
    if not isinstance(html, str):
        return ""

    # Remove script blocks
    before = html
    html = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)
    if html != before:
        report.removed_script = True

    # Remove inline event handlers like onclick="..." or onload='...'
    before = html
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html, flags=re.IGNORECASE)
    if html != before:
        report.removed_inline_handlers = True

    # Remove javascript: in href/src (best-effort)
    before = html
    html = re.sub(r"javascript\s*:", "", html, flags=re.IGNORECASE)
    if html != before:
        report.removed_js_urls = True

    # Block external stylesheet links (best-effort)
    before = html
    html = re.sub(r"(?is)<\s*link\b[^>]*>", "", html)
    if html != before:
        report.removed_link_tags = True

    return html


_STYLE_BLOCK_RE = re.compile(r"(?is)<\s*style\b[^>]*>(.*?)<\s*/\s*style\s*>")
_CSS_SELECTOR_RE = re.compile(r"(?m)^[ \t]*(?!@)([^\n{]+)\{")


def _css_is_scoped_to_wf_root(css: str) -> bool:
    """
    Option A policy:
    - If any top-level selector block does NOT include `.wf-root`, treat as unscoped.
    - At-rules (@media, @keyframes, ...) are allowed; their nested selectors must still be scoped
      but we can't parse deeply without deps. We keep policy conservative.
    """
    if not isinstance(css, str) or not css.strip():
        return False

    # quick check: must mention wf-root somewhere
    if ".wf-root" not in css:
        return False

    for m in _CSS_SELECTOR_RE.finditer(css):
        sel = (m.group(1) or "").strip()
        if ".wf-root" not in sel:
            return False
    return True


def _sanitize_css(css: str, report: NormalizeReport) -> tuple[str, bool]:
    """
    Deterministic CSS policy (no deps):
    - Drop if contains @import or url(
    - Drop if not scoped to `.wf-root`
    - Remove position:fixed (prevents overlaying the host app even if scoped)
    - Clamp z-index to <= 10
    """
    if not isinstance(css, str):
        return "", False

    lowered = css.lower()
    if "@import" in lowered or "url(" in lowered:
        report.style_dropped_import_or_url = True
        return "", True

    if not _css_is_scoped_to_wf_root(css):
        report.style_dropped_unscoped = True
        return "", True

    changed = False

    before = css
    css = re.sub(r"(?i)position\s*:\s*fixed\s*;", "position: static;", css)
    if css != before:
        report.style_sanitized_fixed_removed = True
        changed = True

    def _clamp_z(m: re.Match) -> str:
        try:
            v = int(m.group(1))
        except Exception:
            return m.group(0)
        if v <= 10:
            return m.group(0)
        report.style_sanitized_z_index_clamped = True
        return f"z-index: 10"

    before = css
    css = re.sub(r"(?i)z-index\s*:\s*([0-9]{1,6})", _clamp_z, css)
    if css != before:
        changed = True

    return css, changed


def _sanitize_style_blocks(html: str, report: NormalizeReport) -> str:
    if not isinstance(html, str) or not html:
        return ""

    blocks = list(_STYLE_BLOCK_RE.finditer(html))
    if blocks:
        report.style_found = True

    def _replace(m: re.Match) -> str:
        css = m.group(1) or ""
        sanitized, _ = _sanitize_css(css, report)
        if not sanitized.strip():
            return ""  # drop the entire <style> block
        # keep <style> tag; css is already scoped to .wf-root
        return f"<style>\n{sanitized.strip()}\n</style>"

    return _STYLE_BLOCK_RE.sub(_replace, html)


def _ensure_root_wrapper(
    html: str,
    *,
    ui_name: str,
    theme: WireframeTheme,
    report: NormalizeReport,
) -> str:
    """
    Ensure top-level `.wf-root` container exists.
    - If already present at the start of the fragment, just ensure theme class + data attr exist.
    - Otherwise, wrap with a modern shell (AppBar + content area) to make it look like Ant/Material.
    """
    s = (html or "").strip()
    ui_title = _html.escape(ui_name or "UI")
    theme_class = "wf-theme-ant" if theme == "ant" else "wf-theme-material"

    # detect root at beginning
    root_start_re = re.compile(r'^\s*<div\b[^>]*\bclass\s*=\s*("|\')[^"\']*\bwf-root\b', re.IGNORECASE)
    if root_start_re.search(s):
        report.root_already_present = True

        # ensure data-wf-root="1"
        if re.search(r'\bdata-wf-root\s*=\s*("|\')1("|\')', s, re.IGNORECASE) is None:
            # best-effort: inject into first <div ...>
            s2 = re.sub(r"^\s*<div\b", '<div data-wf-root="1"', s, count=1, flags=re.IGNORECASE)
            if s2 != s:
                s = s2
                report.ensured_root_attrs = True

        # ensure theme class exists in the first class=""
        if re.search(r"\bwf-theme-(ant|material)\b", s, re.IGNORECASE) is None:
            def _add_theme(m: re.Match) -> str:
                q = m.group(1)
                cls = m.group(2) or ""
                return f'class={q}{cls} {theme_class}{q}'

            s2 = re.sub(r'class\s*=\s*("|\')([^"\']*)("|\')', _add_theme, s, count=1, flags=re.IGNORECASE)
            if s2 != s:
                s = s2
                report.ensured_root_attrs = True

        report.theme_selected = theme
        return s

    report.added_root_wrapper = True
    report.theme_selected = theme

    # Modern shell with scoped CSS (must be `.wf-root` scoped per policy)
    css = _modern_scoped_css(theme=theme)
    return f"""
<div class="wf-root {theme_class}" data-wf-root="1">
  <style>
{css}
  </style>
  <header class="wf-appbar" role="banner" aria-label="Page toolbar">
    <div class="wf-appbar__left">
      <div class="wf-title" aria-label="Screen title">{ui_title}</div>
      <div class="wf-subtitle" aria-label="Screen subtitle">Wireframe</div>
    </div>
    <div class="wf-appbar__right" aria-label="Primary actions">
      <button type="button" class="wf-btn wf-btn--primary" aria-label="Primary action">Primary</button>
      <button type="button" class="wf-btn" aria-label="Secondary action">Secondary</button>
    </div>
  </header>
  <main class="wf-main" role="main">
    {s or _empty_state_html()}
  </main>
</div>
""".strip()


def _empty_state_html() -> str:
    return """
<section class="wf-card" role="region" aria-label="Empty state">
  <div class="wf-card__header">
    <div class="wf-card__title">Empty</div>
    <div class="wf-badge">0</div>
  </div>
  <div class="wf-card__body">
    <div class="wf-empty">
      <div class="wf-empty__title">No content yet</div>
      <div class="wf-empty__desc">Describe this screen, and regenerate the wireframe.</div>
      <div class="wf-actions">
        <button type="button" class="wf-btn wf-btn--primary">Generate</button>
        <button type="button" class="wf-btn">Cancel</button>
      </div>
    </div>
  </div>
</section>
""".strip()


def _modern_scoped_css(*, theme: WireframeTheme) -> str:
    # Strictly scoped to `.wf-root` (Option A policy).
    # Keep it lightweight; no external assets, no @import, no url().
    if theme == "material":
        accent = "#6750A4"
        accent2 = "#7D5260"
        bg = "#F7F2FA"
        surface = "#FFFFFF"
        text = "#1C1B1F"
        muted = "#5F5B62"
        border = "rgba(0,0,0,0.12)"
    else:
        # ant-like
        accent = "#1677FF"
        accent2 = "#13C2C2"
        bg = "#F5F5F5"
        surface = "#FFFFFF"
        text = "#1F1F1F"
        muted = "#595959"
        border = "rgba(0,0,0,0.10)"

    return f"""
.wf-root {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", "Noto Sans", Arial, sans-serif;
  color: {text};
  background: {bg};
  border: 1px solid {border};
  border-radius: 14px;
  overflow: hidden;
}}

.wf-root * {{ box-sizing: border-box; }}

.wf-root .wf-appbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: {surface};
  border-bottom: 1px solid {border};
}}

.wf-root .wf-title {{
  font-size: 14px;
  font-weight: 700;
}}

.wf-root .wf-subtitle {{
  margin-top: 2px;
  font-size: 12px;
  color: {muted};
}}

.wf-root .wf-main {{
  padding: 14px;
  display: grid;
  gap: 12px;
}}

.wf-root .wf-card {{
  background: {surface};
  border: 1px solid {border};
  border-radius: 12px;
  overflow: hidden;
}}

.wf-root .wf-card__header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid {border};
  background: rgba(0,0,0,0.02);
}}

.wf-root .wf-card__title {{
  font-weight: 700;
  font-size: 13px;
}}

.wf-root .wf-card__body {{
  padding: 12px;
}}

.wf-root .wf-actions {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}}

.wf-root .wf-btn {{
  appearance: none;
  border: 1px solid {border};
  background: {surface};
  color: {text};
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 12px;
}}

.wf-root .wf-btn--primary {{
  border-color: {accent};
  background: {accent};
  color: #fff;
}}

.wf-root .wf-input {{
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid {border};
  background: {surface};
}}

.wf-root .wf-label {{
  display: block;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
  color: {muted};
}}

.wf-root .wf-grid {{
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 10px;
}}

.wf-root .wf-col-6 {{ grid-column: span 6; }}
.wf-root .wf-col-12 {{ grid-column: span 12; }}

.wf-root .wf-badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid {border};
  color: {muted};
  font-size: 12px;
}}

.wf-root .wf-chip {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px dashed {border};
  color: {muted};
  font-size: 12px;
}}

.wf-root .wf-table {{
  width: 100%;
  border-collapse: collapse;
}}

.wf-root .wf-table th,
.wf-root .wf-table td {{
  padding: 10px 10px;
  border-bottom: 1px solid {border};
  font-size: 12px;
  text-align: left;
}}

.wf-root .wf-table th {{
  color: {muted};
  font-weight: 700;
  background: rgba(0,0,0,0.02);
}}

.wf-root .wf-table__toolbar {{
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-bottom: 10px;
}}

.wf-root .wf-pagination {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
  color: {muted};
  font-size: 12px;
}}

.wf-root .wf-empty {{
  border: 1px dashed {border};
  border-radius: 12px;
  padding: 14px;
  background: rgba(0,0,0,0.01);
}}

.wf-root .wf-empty__title {{
  font-weight: 800;
  margin-bottom: 6px;
}}

.wf-root .wf-empty__desc {{
  color: {muted};
  font-size: 12px;
}}

.wf-root .wf-state {{
  border: 1px dashed {border};
  border-radius: 12px;
  padding: 10px 12px;
  color: {muted};
  font-size: 12px;
}}

.wf-root .wf-state--error {{
  border-color: {accent2};
}}
""".strip()


def fallback_ui_template(*, ui_name: str, theme: WireframeTheme, hint_text: str | None = None) -> str:
    """
    Deterministic modern wireframe fallback.
    Always returns a safe, scoped, body-only fragment with `.wf-root`.
    """
    title = ui_name or "UI"
    content = _deterministic_sections(ui_name=title, hint_text=hint_text or "")
    report = NormalizeReport()
    wrapped = _ensure_root_wrapper(content, ui_name=title, theme=theme, report=report)
    return wrapped


def _deterministic_sections(*, ui_name: str, hint_text: str) -> str:
    t = (hint_text or "")

    wants_table = any(k in t for k in ["목록", "리스트", "list", "조회", "검색", "필터", "readmodel"])
    wants_form = any(k in t for k in ["등록", "생성", "추가", "수정", "편집", "form", "입력"])

    sections: list[str] = []
    sections.append(
        """
<section class="wf-state" role="status" aria-label="Loading state">Loading state placeholder</section>
<section class="wf-state wf-state--error" role="alert" aria-label="Error state">Error state placeholder</section>
""".strip()
    )

    if wants_table:
        sections.append(
            """
<section class="wf-card" role="region" aria-label="List">
  <div class="wf-card__header">
    <div class="wf-card__title">List</div>
    <div class="wf-actions" aria-label="Header actions">
      <span class="wf-chip">Filter</span>
      <span class="wf-chip">Sort</span>
    </div>
  </div>
  <div class="wf-card__body">
    <div class="wf-table__toolbar" aria-label="Table toolbar">
      <div style="min-width: 220px;">
        <label class="wf-label">Search</label>
        <input class="wf-input" type="text" placeholder="Search..." />
      </div>
      <div class="wf-actions">
        <button type="button" class="wf-btn">Filter</button>
        <button type="button" class="wf-btn wf-btn--primary">New</button>
      </div>
    </div>
    <table class="wf-table" aria-label="Data table">
      <thead>
        <tr>
          <th>Column A</th>
          <th>Column B</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>...</td><td>...</td><td><span class="wf-badge">...</span></td><td><button type="button" class="wf-btn">View</button></td></tr>
        <tr><td>...</td><td>...</td><td><span class="wf-badge">...</span></td><td><button type="button" class="wf-btn">Edit</button></td></tr>
        <tr><td>...</td><td>...</td><td><span class="wf-badge">...</span></td><td><button type="button" class="wf-btn">Delete</button></td></tr>
      </tbody>
    </table>
    <div class="wf-pagination" aria-label="Pagination">
      <div>Showing 1–10 of 100</div>
      <div class="wf-actions">
        <button type="button" class="wf-btn" aria-label="Previous page">Prev</button>
        <button type="button" class="wf-btn" aria-label="Next page">Next</button>
      </div>
    </div>
  </div>
</section>
""".strip()
        )

    if wants_form:
        sections.append(
            """
<section class="wf-card" role="region" aria-label="Form">
  <div class="wf-card__header">
    <div class="wf-card__title">Form</div>
    <div class="wf-badge">Draft</div>
  </div>
  <div class="wf-card__body">
    <div class="wf-grid">
      <div class="wf-col-6">
        <label class="wf-label">Field A (required)</label>
        <input class="wf-input" type="text" placeholder="Enter..." aria-required="true" />
        <div class="wf-state" role="note">Help text / validation placeholder</div>
      </div>
      <div class="wf-col-6">
        <label class="wf-label">Field B</label>
        <input class="wf-input" type="text" placeholder="Enter..." />
        <div class="wf-state" role="note">Help text placeholder</div>
      </div>
      <div class="wf-col-12">
        <label class="wf-label">Notes</label>
        <textarea class="wf-input" rows="3" placeholder="..." ></textarea>
      </div>
    </div>
    <div class="wf-actions" aria-label="Form actions">
      <button type="button" class="wf-btn wf-btn--primary">Save</button>
      <button type="button" class="wf-btn">Cancel</button>
    </div>
  </div>
</section>
""".strip()
        )

    if not wants_table and not wants_form:
        sections.append(_empty_state_html())

    return "\n".join(sections).strip()


def normalize_ui_template(
    raw_html: str | None,
    *,
    ui_name: str,
    theme_hint: str | None = None,
) -> Tuple[str, NormalizeReport]:
    """
    Deterministic normalization (E2):
    - Enforce body-only fragment
    - Baseline sanitization: script/on*/javascript:
    - Allow <style> only when scoped to `.wf-root`, with no @import/url()
    - Ensure top-level `.wf-root` wrapper
    - Enforce MAX_TEMPLATE_LEN (50KB): drop <style> first; if still too big, fallback
    """
    report = NormalizeReport()
    report.len_before = len(raw_html or "")

    theme = _select_theme(theme_hint=theme_hint, html_text=raw_html)
    report.theme_selected = theme

    s = raw_html or ""
    s, stripped = strip_markdown_fences(s)
    report.stripped_markdown_fences = stripped

    s, removed_doc = _remove_document_root(s)
    report.removed_doc_root = removed_doc

    s = _sanitize_baseline(s, report)
    s = _sanitize_style_blocks(s, report)

    # Wrap/ensure root
    s = _ensure_root_wrapper(s, ui_name=ui_name, theme=theme, report=report)

    # Size policy: try dropping all <style> blocks first (deterministic)
    if len(s) > MAX_TEMPLATE_LEN:
        s2 = re.sub(r"(?is)<\s*style\b[^>]*>.*?<\s*/\s*style\s*>", "", s).strip()
        if s2 != s:
            report.size_truncated_by_dropping_style = True
        s = s2

    # If still too large, fallback
    if len(s) > MAX_TEMPLATE_LEN or not s.strip():
        report.fallback_used = True
        s = fallback_ui_template(ui_name=ui_name, theme=theme, hint_text=theme_hint)

    # Final baseline pass (belt-and-suspenders)
    s = _sanitize_baseline(s, report)
    s, _ = _remove_document_root(s)

    report.len_after = len(s)
    return s, report


