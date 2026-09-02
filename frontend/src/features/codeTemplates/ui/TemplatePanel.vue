<script setup>
/**
 * Template 탭 — 템플릿 기반 코드 생성.
 *
 * Code 탭(Claude Code TUI)과 별개다. 그쪽은 바이브 코딩이고 여기는 결정적
 * 생성이다 — 같은 모델과 같은 템플릿이면 같은 결과가 나온다.
 *
 * 렌더링을 브라우저에서 하는 이유는 템플릿이 자기 Handlebars 헬퍼를
 * JavaScript 로 들고 다니기 때문이다. 자세한 것은 `renderer.js` 주석.
 */
import { computed, onMounted, ref, watch } from 'vue'
import JSZip from 'jszip'
import { getContext, listFiles, listSessions, listSets } from '../api.js'
import { renderAll } from '../renderer.js'
import { buildTree, collapseChains, firstFile } from '../tree.js'
import GeneratedTree from './GeneratedTree.vue'
import GeneratedViewer from './GeneratedViewer.vue'

// POSCO DX 템플릿이 기본이자 사실상 유일한 묶음이다. 다른 것이 받아져 있을
// 때만 고를 수 있게 한다 — 하나뿐이면 선택지를 보여 줄 이유가 없다.
const DEFAULT_SET = 'template-poscodx'

const sets = ref([])
const setName = ref(DEFAULT_SET)
const templatesRoot = ref('')
const setsHint = ref(null)

const sessions = ref([])
const sessionId = ref('')

// 생성 옵션은 템플릿이 정한다 — `_template/configuration.html` 이
// `<text-field :value.sync="value.serviceId" label="서비스 ID">` 처럼 선언한다.
// 기준 구현도 그 파일로 폼을 만든다. 여기서 항목을 지어내지 않는다.
const optionFields = ref([])
const options = ref({})
// 사용자가 손댄 항목은 세션을 바꿔도 지킨다.
const editedKeys = ref(new Set())

const loading = ref(false)
const error = ref(null)
const result = ref(null)
const selected = ref(null)

const hasChoice = computed(() => sets.value.length > 1)
const currentSession = computed(() => sessions.value.find((s) => s.id === sessionId.value))
const fileCount = computed(() => result.value?.files?.length || 0)
const serviceId = computed(() => options.value.serviceId || '')

/** 세션 이름에서 자바 패키지 한 마디로 쓸 만한 기본값을 만든다. */
function suggestServiceId(name) {
  const ascii = (name || '').replace(/[^0-9A-Za-z]+/g, '')
  return ascii ? ascii.charAt(0).toLowerCase() + ascii.slice(1) : ''
}

// 세션 이름에서 만든 값을 채워 두되, 사용자가 고친 항목은 건드리지 않는다.
watch([sessionId, optionFields], () => {
  const suggested = suggestServiceId(currentSession.value?.name) || sessionId.value
  const next = { ...options.value }
  for (const f of optionFields.value) {
    if (editedKeys.value.has(f.key)) continue
    next[f.key] = f.key === 'serviceId' ? suggested : (next[f.key] ?? '')
  }
  options.value = next
})

function editOption(key, value) {
  options.value = { ...options.value, [key]: value }
  editedKeys.value = new Set(editedKeys.value).add(key)
}

onMounted(async () => {
  try {
    const [s, d] = await Promise.all([listSets(), listSessions()])
    sets.value = s.sets || []
    templatesRoot.value = s.templatesRoot || ''
    setsHint.value = s.hint || null
    // 기본 묶음이 있으면 그것을, 없으면 받아져 있는 첫 번째를 쓴다.
    const names = sets.value.map((x) => x.name)
    setName.value = names.includes(DEFAULT_SET) ? DEFAULT_SET : names[0] || ''
    sessions.value = d.sessions || []
    if (sessions.value.length) sessionId.value = sessions.value[0].id
    if (setName.value) await loadOptions()
  } catch (e) {
    error.value = e.message
  }
})

/** 묶음이 요구하는 옵션 목록을 읽어 온다. 묶음을 바꾸면 다시 읽는다. */
async function loadOptions() {
  const { options: fields } = await listFiles(setName.value)
  optionFields.value = fields || []
}

watch(setName, async (name) => {
  if (!name) return
  try { await loadOptions() } catch (e) { error.value = e.message }
})

async function generate() {
  error.value = null
  result.value = null
  selected.value = null
  const missing = optionFields.value.filter((f) => !String(options.value[f.key] || '').trim())
  if (!setName.value || !sessionId.value || missing.length) {
    error.value = missing.length
      ? `${missing.map((f) => f.label).join(', ')} 를 입력하세요.`
      : '세션을 지정하세요.'
    return
  }
  loading.value = true
  try {
    const [{ files: templates }, ctx] = await Promise.all([
      listFiles(setName.value),
      getContext(sessionId.value, options.value.serviceId || ''),
    ])
    result.value = renderAll(templates, ctx)
    selected.value = firstFile(collapseChains(buildTree(result.value.files)))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function download() {
  if (!fileCount.value) return
  const zip = new JSZip()
  for (const f of result.value.files) zip.file(f.path, f.content)
  const blob = await zip.generateAsync({ type: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${serviceId.value || 'generated'}-source.zip`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="tpl">
    <header class="tpl__toolbar">
      <div class="tpl__field">
        <label>세션</label>
        <select v-model="sessionId" :disabled="!sessions.length">
          <option v-for="s in sessions" :key="s.id" :value="s.id">
            {{ s.name }} — BC {{ s.boundedContexts }}
          </option>
        </select>
      </div>

      <!-- 템플릿이 선언한 항목만 그린다. 화면이 옵션을 정하지 않는다. -->
      <div v-for="f in optionFields" :key="f.key" class="tpl__field">
        <label>{{ f.label }}</label>
        <input
          :value="options[f.key] || ''"
          :placeholder="f.key"
          @input="editOption(f.key, $event.target.value)"
        />
      </div>

      <div v-if="hasChoice" class="tpl__field">
        <label>템플릿</label>
        <select v-model="setName">
          <option v-for="s in sets" :key="s.name" :value="s.name">
            {{ s.name }} ({{ s.fileCount }})
          </option>
        </select>
      </div>

      <button class="tpl__btn tpl__btn--primary" :disabled="loading" @click="generate">
        {{ loading ? '생성 중…' : '코드 생성' }}
      </button>
      <button class="tpl__btn" :disabled="!fileCount" @click="download">
        ZIP 내려받기<span v-if="fileCount"> ({{ fileCount }})</span>
      </button>

      <div class="tpl__spacer"></div>
      <span class="tpl__pkg">
        com.poscodx.<b>{{ serviceId || 'serviceId' }}</b>.&lt;boundedContext&gt;
        <template v-if="!hasChoice"> · {{ setName || '템플릿 없음' }}</template>
      </span>
    </header>

    <p v-if="setsHint" class="tpl__banner tpl__banner--warn">
      {{ setsHint }} <span class="tpl__dim">{{ templatesRoot }}</span>
    </p>
    <p v-if="error" class="tpl__banner tpl__banner--err">{{ error }}</p>
    <p v-if="result?.errors?.length" class="tpl__banner tpl__banner--warn">
      템플릿 {{ result.errors.length }}건이 렌더링되지 않았습니다 —
      <span class="tpl__dim">{{ result.errors[0].template }}: {{ result.errors[0].error }}</span>
    </p>

    <div v-if="result" class="tpl__body">
      <nav class="tpl__tree">
        <GeneratedTree
          :files="result.files"
          :active-path="selected?.path || ''"
          @open="selected = $event"
        />
      </nav>
      <GeneratedViewer :file="selected" />
    </div>

    <div v-else class="tpl__empty">
      <p>이벤트 스토밍 요소로 POSCO DX 5계층 Java 프로젝트를 생성합니다.</p>
      <p class="tpl__dim">세션과 Service ID 를 확인하고 <b>코드 생성</b>을 누르세요.</p>
    </div>
  </div>
</template>

<style scoped>
.tpl {
  display: flex; flex-direction: column; height: 100%; min-height: 0;
  background: var(--ccw-bg); color: var(--ccw-text);
}

.tpl__toolbar {
  display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap;
  padding: 8px 12px; background: var(--ccw-bg-elevated);
  border-bottom: 1px solid var(--ccw-border);
}
.tpl__field { display: flex; flex-direction: column; gap: 3px; }
.tpl__field label { font-size: 11px; color: var(--ccw-text-dim); }
.tpl__field select,
.tpl__field input {
  padding: 4px 8px; font-size: 12px; font-family: inherit;
  color: var(--ccw-text); background: var(--ccw-bg);
  border: 1px solid var(--ccw-border); border-radius: 4px; min-width: 190px;
}
.tpl__field input { min-width: 130px; }
.tpl__field select:focus, .tpl__field input:focus {
  outline: none; border-color: var(--ccw-accent);
}

.tpl__btn {
  padding: 5px 12px; font-size: 12px; font-family: inherit; cursor: pointer;
  color: var(--ccw-text); background: var(--ccw-bg);
  border: 1px solid var(--ccw-border); border-radius: 4px;
}
.tpl__btn:hover:not(:disabled) { background: var(--ccw-hover); }
.tpl__btn:disabled { opacity: .45; cursor: default; }
.tpl__btn--primary {
  color: #fff; background: var(--ccw-accent); border-color: var(--ccw-accent);
}
.tpl__btn--primary:hover:not(:disabled) { background: var(--ccw-accent-strong); }

.tpl__spacer { flex: 1; }
.tpl__pkg {
  font-size: 11px; color: var(--ccw-text-dim); padding-bottom: 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.tpl__pkg b { color: var(--ccw-text-muted); font-weight: 600; }

.tpl__banner { margin: 0; padding: 6px 12px; font-size: 12px;
  border-bottom: 1px solid var(--ccw-border); }
.tpl__banner--warn { color: var(--ccw-yellow); }
.tpl__banner--err { color: var(--ccw-red); }
.tpl__dim { color: var(--ccw-text-dim); }

.tpl__body { display: grid; grid-template-columns: 320px 1fr; flex: 1; min-height: 0; }
.tpl__tree { overflow: auto; border-right: 1px solid var(--ccw-border); }

.tpl__empty {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 6px; font-size: 13px; color: var(--ccw-text-muted);
}
.tpl__empty p { margin: 0; }
</style>
