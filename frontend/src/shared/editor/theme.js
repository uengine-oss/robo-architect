/**
 * CodeMirror 공용 테마 — Claude Code 편집기와 Template 뷰어가 같이 쓴다.
 *
 * FileEditorPane 안에만 있던 것을 옮겼다. 코드를 보여 주는 화면이 둘이 되면서
 * 한쪽만 손보면 서로 다른 색이 되기 때문이다. 동작은 그대로다.
 */
import { EditorView } from '@codemirror/view'
import { HighlightStyle } from '@codemirror/language'
import { tags as t } from '@lezer/highlight'

export const tokyoNightHighlight = HighlightStyle.define([
  { tag: t.keyword, color: 'var(--ccw-purple)' },
  { tag: [t.controlKeyword, t.moduleKeyword, t.operatorKeyword], color: 'var(--ccw-purple)' },
  { tag: [t.string, t.special(t.string)], color: 'var(--ccw-green)' },
  { tag: t.regexp, color: 'var(--ccw-cyan)' },
  { tag: t.escape, color: 'var(--ccw-cyan)' },
  { tag: t.number, color: 'var(--ccw-orange)' },
  { tag: t.bool, color: 'var(--ccw-orange)' },
  { tag: t.null, color: 'var(--ccw-orange)' },
  { tag: [t.comment, t.lineComment, t.blockComment], color: 'var(--ccw-text-dim)', fontStyle: 'italic' },
  { tag: t.atom, color: 'var(--ccw-purple)' },
  { tag: t.heading, color: 'var(--ccw-accent)', fontWeight: 'bold' },
  { tag: t.strong, color: 'var(--ccw-text)', fontWeight: 'bold' },
  { tag: t.emphasis, color: 'var(--ccw-text)', fontStyle: 'italic' },
  { tag: t.link, color: 'var(--ccw-teal)', textDecoration: 'underline' },
  { tag: t.url, color: 'var(--ccw-teal)', textDecoration: 'underline' },
  { tag: t.list, color: 'var(--ccw-accent)' },
  { tag: t.quote, color: 'var(--ccw-green)' },
  { tag: [t.variableName, t.propertyName], color: 'var(--ccw-text)' },
  { tag: t.function(t.variableName), color: 'var(--ccw-accent)' },
  { tag: t.definition(t.variableName), color: 'var(--ccw-text)' },
  { tag: [t.typeName, t.className], color: 'var(--ccw-cyan)' },
  { tag: t.operator, color: 'var(--ccw-cyan)' },
  { tag: [t.bracket, t.punctuation, t.separator], color: 'var(--ccw-text-muted)' },
  { tag: t.tagName, color: 'var(--ccw-red)' },
  { tag: t.attributeName, color: 'var(--ccw-yellow)' },
  { tag: t.attributeValue, color: 'var(--ccw-green)' },
  { tag: t.meta, color: 'var(--ccw-accent)' },
  { tag: t.invalid, color: 'var(--ccw-red)' },
])

export const tokyoNightEditorTheme = EditorView.theme(
  {
    '&': {
      height: '100%',
      fontSize: '13px',
      color: 'var(--ccw-text)',
      backgroundColor: 'var(--ccw-bg)',
    },
    '.cm-content': {
      caretColor: 'var(--ccw-text)',
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    },
    '.cm-scroller': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--ccw-text)' },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
      backgroundColor: 'var(--ccw-selection)',
    },
    '.cm-activeLine': { backgroundColor: 'var(--ccw-hover)' },
    '.cm-gutters': {
      backgroundColor: 'var(--ccw-bg)',
      color: 'var(--ccw-gutter)',
      border: 'none',
      borderRight: '1px solid var(--ccw-border)',
    },
    '.cm-lineNumbers .cm-gutterElement': {
      color: 'var(--ccw-gutter)',
      padding: '0 12px 0 8px',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'var(--ccw-hover)',
      color: 'var(--ccw-accent)',
    },
    '.cm-matchingBracket, .cm-nonmatchingBracket': {
      backgroundColor: 'var(--ccw-active)',
      color: 'inherit',
    },
  },
  { dark: true },
)
