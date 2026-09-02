<script setup>
/**
 * 생성 결과 코드 뷰어 — 읽기 전용 CodeMirror.
 *
 * 편집은 하지 않는다. 여기 보이는 것은 템플릿과 모델에서 결정적으로 나온
 * 결과이므로, 고쳐야 할 것은 템플릿이나 모델이지 이 화면이 아니다.
 */
import { onBeforeUnmount, ref, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { syntaxHighlighting, bracketMatching } from '@codemirror/language'
import { java } from '@codemirror/lang-java'
import { xml } from '@codemirror/lang-xml'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { markdown } from '@codemirror/lang-markdown'
import { tokyoNightEditorTheme, tokyoNightHighlight } from '@/shared/editor/theme.js'
import FileIcon from '@/shared/ui/FileIcon.vue'

const props = defineProps({
  file: { type: Object, default: null },  // { path, content, template, forEach }
})

const host = ref(null)
let view = null

function languageFor(path) {
  const p = (path || '').toLowerCase()
  if (p.endsWith('.java')) return [java()]
  if (p.endsWith('.xml') || p.endsWith('.html')) return [xml()]
  if (p.endsWith('.json')) return [json()]
  if (p.endsWith('.yml') || p.endsWith('.yaml')) return [yaml()]
  if (p.endsWith('.md')) return [markdown()]
  return []
}

function destroy() {
  if (view) { view.destroy(); view = null }
}

function mount() {
  destroy()
  if (!host.value || !props.file) return
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.file.content || '',
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        bracketMatching(),
        syntaxHighlighting(tokyoNightHighlight, { fallback: true }),
        languageFor(props.file.path),
        EditorView.editable.of(false),
        EditorState.readOnly.of(true),
        tokyoNightEditorTheme,
      ],
    }),
  })
}

watch(() => props.file, mount, { immediate: false, flush: 'post' })
watch(host, mount, { flush: 'post' })
onBeforeUnmount(destroy)

async function copy() {
  if (!props.file) return
  try { await navigator.clipboard.writeText(props.file.content || '') } catch { /* 권한 없으면 무시 */ }
}
</script>

<template>
  <section class="gv">
    <header v-if="file" class="gv__head">
      <FileIcon :name="file.path" />
      <code class="gv__path">{{ file.path }}</code>
      <span class="gv__meta">{{ file.template }} · forEach {{ file.forEach }}</span>
      <button class="gv__copy" title="내용 복사" @click="copy">복사</button>
    </header>
    <div v-if="file" ref="host" class="gv__editor"></div>
    <p v-else class="gv__empty">왼쪽 탐색기에서 파일을 고르세요.</p>
  </section>
</template>

<style scoped>
.gv { display: flex; flex-direction: column; min-height: 0; height: 100%;
  background: var(--ccw-bg); overflow: hidden; }
.gv__head { display: flex; align-items: center; gap: 10px; padding: 6px 12px;
  background: var(--ccw-bg-elevated); border-bottom: 1px solid var(--ccw-border);
  font-size: 12px; color: var(--ccw-text); }
.gv__path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.gv__meta { margin-left: auto; color: var(--ccw-text-dim); white-space: nowrap; font-size: 11px; }
.gv__copy { border: 1px solid var(--ccw-border); background: var(--ccw-bg);
  color: var(--ccw-text); border-radius: 4px; font-size: 11px; padding: 3px 9px;
  cursor: pointer; font-family: inherit; }
.gv__copy:hover { background: var(--ccw-hover); }
.gv__editor { flex: 1; min-height: 0; overflow: hidden; }
.gv__empty { padding: 16px; color: var(--ccw-text-dim); font-size: 13px; }
</style>
