<script setup>
/**
 * 템플릿 원본 보기 · 수정 (TPL-1).
 *
 * **왜 있어야 하나.** 생성 결과가 마음에 안 들면 고쳐야 할 것은 템플릿인데, 그것이
 * 산출물 안의 파일이라 한 줄을 고치려면 **전체를 다시 구워 20여 대에 재설치**해야
 * 했다. 이제 고친 것은 중앙 DB 에 쌓이고, 다른 PC 는 다음 조회부터 그것을 쓴다.
 *
 * **원본은 사라지지 않는다.** 산출물의 파일이 출고 상태 그대로 남아 있어서,
 * 되돌리기는 복사본을 되살리는 것이 아니라 **DB 행을 지우는 것**이다. 그래서 언제든
 * 원본과 나란히 볼 수 있다.
 *
 * **고치는 것은 관리자만이다.** 본문 끝의 `<function>` 블록은 Handlebars 헬퍼를
 * 담은 JavaScript 이고, 렌더러가 `new Function` 으로 **실제로 실행한다**(`renderer.js`).
 * 즉 여기에 글을 쓰는 것은 앱 안에서 코드를 돌리는 것과 같다. 관리자가 아니면
 * 읽기만 되고, 저장할 때마다 이력과 로그가 남는다.
 */
import { computed, ref, watch } from 'vue'
import { getTemplateFile, revertTemplateFile, saveTemplateFile } from '../api.js'
import { useAuthStore } from '@/features/auth/auth.store.js'
import GeneratedTree from './GeneratedTree.vue'

const props = defineProps({
  setName: { type: String, required: true },
  files: { type: Array, default: () => [] },
})
const emit = defineEmits(['changed'])

const auth = useAuthStore()
const canEdit = computed(() => !!auth.isAdmin)

const path = ref('')
const detail = ref(null)
const draft = ref('')
const busy = ref(false)
const error = ref(null)
const notice = ref(null)
const showOriginal = ref(false)

/**
 * **원본의 폴더 구조 그대로 본다.**
 *
 * 처음에는 상대경로를 한 줄씩 늘어놓았는데, 37장이 평평하게 쏟아져 어느 계층의
 * 무엇인지 읽히지 않았다(사용자 지적). 생성 결과와 **같은 트리 부품**을 쓴다 —
 * 두 번째 탐색기를 만들면 둘이 어긋난다.
 */
const treeFiles = computed(() =>
  props.files.map((f) => ({ ...f, path: f.relativePath })),
)
/** 원본과 다른 장들. 트리가 여기에 점을 찍는다. */
const markedPaths = computed(
  () => new Set(props.files.filter((f) => f.source === 'db').map((f) => f.relativePath)),
)

const dirty = computed(() => !!detail.value && draft.value !== detail.value.current)
const modified = computed(() => detail.value?.source === 'db')

async function open(next) {
  path.value = next
  error.value = null
  notice.value = null
  showOriginal.value = false
  detail.value = null
  busy.value = true
  try {
    detail.value = await getTemplateFile(props.setName, next)
    draft.value = detail.value.current || ''
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

// 묶음을 바꾸면 열어 둔 장은 더 이상 그 묶음의 것이 아니다.
watch(() => props.setName, () => { path.value = ''; detail.value = null })

async function save() {
  if (!canEdit.value || !dirty.value || busy.value) return
  busy.value = true
  error.value = null
  try {
    await saveTemplateFile(props.setName, path.value, draft.value)
    notice.value = '저장했습니다. 이제 모든 PC 가 이 템플릿을 씁니다.'
    await open(path.value)
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function revert() {
  if (!canEdit.value || !modified.value || busy.value) return
  busy.value = true
  error.value = null
  try {
    await revertTemplateFile(props.setName, path.value)
    notice.value = '원본으로 되돌렸습니다.'
    await open(path.value)
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

/** 이력 한 판을 편집기에 올린다. 저장하기 전에는 아무것도 바뀌지 않는다. */
async function loadVersion(id) {
  busy.value = true
  error.value = null
  try {
    const v = await getTemplateFile(props.setName, path.value, id)
    draft.value = v.current || ''
    notice.value = '이력 판을 불러왔습니다. 저장해야 적용됩니다.'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function when(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<template>
  <div class="tsrc">
    <nav class="tsrc__list">
      <GeneratedTree
        :files="treeFiles"
        :active-path="path"
        :marked="markedPaths"
        @open="open($event.relativePath)"
      />
    </nav>

    <section v-if="detail" class="tsrc__pane">
      <header class="tsrc__bar">
        <b class="tsrc__path">{{ detail.path }}</b>
        <!-- 손댄 것만 말한다. 안 고친 장에까지 '원본 그대로' 를 붙이면 37줄이 전부
             같은 말을 하고, 정작 다른 한 장이 묻힌다(사용자 지적). -->
        <span v-if="modified" class="tsrc__meta">
          {{ detail.updatedBy || '누군가' }} · {{ when(detail.updatedAt) }} 수정
        </span>

        <div class="tsrc__spacer"></div>

        <button v-if="detail.original !== null" class="tsrc__btn" @click="showOriginal = !showOriginal">
          {{ showOriginal ? '수정본 보기' : '원본 보기' }}
        </button>
        <button class="tsrc__btn" :disabled="!canEdit || !modified || busy" @click="revert">
          원본으로 되돌리기
        </button>
        <button class="tsrc__btn tsrc__btn--primary" :disabled="!canEdit || !dirty || busy" @click="save">
          {{ busy ? '저장 중…' : '저장' }}
        </button>
      </header>

      <p v-if="!canEdit" class="tsrc__note">
        읽기 전용입니다 — 템플릿 수정은 <b>관리자</b>만 할 수 있습니다.
      </p>
      <p v-if="detail.originalChanged" class="tsrc__note tsrc__note--warn">
        <b>출고 템플릿이 그 뒤에 바뀌었습니다.</b>
        이 수정본이 새 원본을 덮고 있습니다 — <b>원본 보기</b>로 비교한 뒤,
        새것을 쓰려면 <b>원본으로 되돌리기</b>를 누르세요.
      </p>
      <p v-if="detail.hasFunctions" class="tsrc__note tsrc__note--warn">
        이 템플릿은 <code>&lt;function&gt;</code> 블록을 담고 있습니다.
        그 안의 JavaScript 는 코드 생성을 누를 때 <b>앱 안에서 실행됩니다.</b>
      </p>
      <p v-if="error" class="tsrc__note tsrc__note--err">{{ error }}</p>
      <p v-else-if="notice" class="tsrc__note tsrc__note--ok">{{ notice }}</p>

      <textarea
        v-if="!showOriginal"
        v-model="draft"
        class="tsrc__editor"
        spellcheck="false"
        :readonly="!canEdit"
      ></textarea>
      <pre v-else class="tsrc__editor tsrc__editor--ro">{{ detail.original }}</pre>

      <footer v-if="detail.history.length" class="tsrc__hist">
        <span class="tsrc__histlabel">이력</span>
        <button
          v-for="h in detail.history.slice(0, 8)"
          :key="h.id"
          class="tsrc__chip"
          :disabled="h.action !== 'save'"
          :title="h.action === 'save' ? '이 판을 편집기에 올립니다' : '원본으로 되돌린 기록'"
          @click="loadVersion(h.id)"
        >
          {{ when(h.savedAt) }} · {{ h.savedBy || '?' }}{{ h.action === 'revert' ? ' · 되돌림' : '' }}
        </button>
      </footer>
    </section>

    <section v-else class="tsrc__empty">
      <p>왼쪽에서 템플릿을 고르면 원문이 보입니다.</p>
      <p class="tsrc__dim">
        고친 템플릿은 중앙 DB 에 저장되어 <b>모든 PC 에 바로 적용</b>됩니다 — 다시 굽지 않습니다.
      </p>
    </section>
  </div>
</template>

<style scoped>
.tsrc { display: grid; grid-template-columns: 320px 1fr; flex: 1; min-height: 0; }

.tsrc__list { overflow: auto; border-right: 1px solid var(--ccw-border); padding: 4px 0; }
.tsrc__item {
  display: flex; align-items: center; gap: 6px; width: 100%;
  padding: 4px 10px; border: 0; background: none; cursor: pointer;
  font: inherit; font-size: 12px; color: var(--ccw-text); text-align: left;
}
.tsrc__item:hover { background: var(--ccw-hover); }
.tsrc__item--on { background: var(--ccw-hover); font-weight: 600; }
.tsrc__name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tsrc__tag {
  font-size: 10px; padding: 0 5px; border-radius: 8px;
  color: #fff; background: var(--ccw-accent);
}
.tsrc__tag--dim { color: var(--ccw-text-dim); background: transparent; border: 1px solid var(--ccw-border); }

.tsrc__pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.tsrc__bar {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  border-bottom: 1px solid var(--ccw-border); background: var(--ccw-bg-elevated);
}
.tsrc__path { font-size: 12px; font-family: ui-monospace, Menlo, Consolas, monospace; }
.tsrc__meta { font-size: 11px; color: var(--ccw-text-dim); }
.tsrc__spacer { flex: 1; }
.tsrc__btn {
  padding: 3px 10px; font-size: 12px; font-family: inherit; cursor: pointer;
  color: var(--ccw-text); background: var(--ccw-bg);
  border: 1px solid var(--ccw-border); border-radius: 4px;
}
.tsrc__btn:hover:not(:disabled) { background: var(--ccw-hover); }
.tsrc__btn:disabled { opacity: .45; cursor: default; }
.tsrc__btn--primary { color: #fff; background: var(--ccw-accent); border-color: var(--ccw-accent); }

.tsrc__note { margin: 0; padding: 5px 10px; font-size: 12px; color: var(--ccw-text-dim);
  border-bottom: 1px solid var(--ccw-border); }
.tsrc__note--warn { color: var(--ccw-yellow); }
.tsrc__note--err { color: var(--ccw-red); }
.tsrc__note--ok { color: var(--ccw-green, var(--ccw-text-muted)); }

.tsrc__editor {
  flex: 1; min-height: 0; width: 100%; box-sizing: border-box; resize: none;
  padding: 10px; border: 0; outline: none; white-space: pre; overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px; line-height: 1.5;
  color: var(--ccw-text); background: var(--ccw-bg);
}
.tsrc__editor--ro { margin: 0; opacity: .85; }

.tsrc__hist {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 5px 10px; border-top: 1px solid var(--ccw-border);
}
.tsrc__histlabel { font-size: 11px; color: var(--ccw-text-dim); }
.tsrc__chip {
  font: inherit; font-size: 11px; padding: 1px 7px; cursor: pointer;
  color: var(--ccw-text-muted); background: var(--ccw-bg);
  border: 1px solid var(--ccw-border); border-radius: 9px;
}
.tsrc__chip:disabled { opacity: .5; cursor: default; }

.tsrc__empty {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 6px; font-size: 13px; color: var(--ccw-text-muted);
}
.tsrc__empty p { margin: 0; }
.tsrc__dim { color: var(--ccw-text-dim); }
</style>
