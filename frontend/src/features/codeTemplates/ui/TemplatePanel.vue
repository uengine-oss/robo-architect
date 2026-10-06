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
import { useProjectsStore } from '@/features/projects/projects.store.js'
import { renderAll } from '../renderer.js'
import { buildTree, collapseChains, firstFile } from '../tree.js'
import GeneratedTree from './GeneratedTree.vue'
import GeneratedViewer from './GeneratedViewer.vue'
import TemplateSourcePanel from './TemplateSourcePanel.vue'

// POSCO DX 템플릿이 기본이자 사실상 유일한 묶음이다. 다른 것이 받아져 있을
// 때만 고를 수 있게 한다 — 하나뿐이면 선택지를 보여 줄 이유가 없다.
const DEFAULT_SET = 'template-poscodx'

const projects = useProjectsStore()
/** 지금 고른 프로젝트의 이름. 세션은 이 프로젝트 안의 것들이다. */
const projectName = computed(() => projects.currentName || '프로젝트')

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
// 묶음의 템플릿 전체. 생성에도 쓰고 **원본 보기/수정**에도 쓴다 — 같은 응답이다.
const templateFiles = ref([])
// 원본 보기로 바꾸면 생성 결과 자리에 템플릿 편집기가 들어온다 (TPL-1).
const sourceMode = ref(false)
// 사용자가 손댄 항목은 세션을 바꿔도 지킨다.
const editedKeys = ref(new Set())

const loading = ref(false)
const error = ref(null)
const result = ref(null)
const selected = ref(null)

const hasChoice = computed(() => sets.value.length > 1)
const currentSession = computed(() => sessions.value.find((s) => s.id === sessionId.value))
const fileCount = computed(() => result.value?.files?.length || 0)
const overriddenCount = computed(
  () => templateFiles.value.filter((f) => f.source === 'db').length,
)
const serviceId = computed(() => options.value.serviceId || '')

/** 자바 패키지 한 마디로 쓸 만한 기본값을 만든다. 영문이 없으면 빈 값이다. */
function suggestServiceId(name) {
  const ascii = (name || '').replace(/[^0-9A-Za-z]+/g, '')
  return ascii ? ascii.charAt(0).toLowerCase() + ascii.slice(1) : ''
}

/**
 * 기본값은 **프로젝트 이름**에서 만든다.
 *
 * 전에는 세션 이름(= 첫 프로세스 이름)에서 만들고, 영문이 하나도 없으면
 * **세션 아이디로 떨어졌다** — 그래서 패키지가 `com.poscodx.0eb8e37f.…` 가 됐다.
 * 사람이 읽을 수 없는 값이고 자바 패키지로도 뜻이 없다. 이름이 전부 한글이면
 * **비워 둔다** — 비면 생성 버튼이 입력을 요구하므로, 지어내는 것보다 낫다.
 */
function suggestedServiceId() {
  return suggestServiceId(projectName.value) || suggestServiceId(currentSession.value?.name) || ''
}

// 기본값을 채워 두되, 사용자가 고친 항목은 건드리지 않는다.
watch([sessionId, optionFields, projectName], () => {
  const suggested = suggestedServiceId()
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

/** 묶음의 템플릿과 옵션을 읽어 온다. 묶음을 바꾸거나 템플릿을 고치면 다시 읽는다. */
async function loadOptions() {
  const { options: fields, files } = await listFiles(setName.value)
  optionFields.value = fields || []
  templateFiles.value = files || []
}

/**
 * 템플릿이 바뀌었다. **생성해 둔 결과는 더 이상 그 템플릿의 산물이 아니다** —
 * 지우고 다시 누르게 한다. 남겨 두면 어느 템플릿으로 만든 것인지 알 수 없다.
 */
async function onTemplateChanged() {
  result.value = null
  selected.value = null
  try { await loadOptions() } catch (e) { error.value = e.message }
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
        <label>프로젝트 · 세션</label>
        <select v-model="sessionId" :disabled="!sessions.length">
          <!-- 세션 아이디(`0eb8e37f`)는 사람이 고를 수 있는 이름이 아니다.
               **프로젝트 이름**을 앞에 두고, 세션은 그 안의 판으로 읽히게 한다. -->
          <option v-for="s in sessions" :key="s.id" :value="s.id" :title="s.id">
            {{ projectName }} · {{ s.name === s.id ? '이름 없는 판' : s.name }} — BC {{ s.boundedContexts }}
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
      <!-- 생성 결과가 마음에 안 들면 고칠 것은 템플릿이다. 그 자리를 여기 둔다. -->
      <button
        class="tpl__btn"
        :class="{ 'tpl__btn--on': sourceMode }"
        :disabled="!templateFiles.length"
        @click="sourceMode = !sourceMode"
      >
        템플릿 수정모드<span v-if="overriddenCount"> ({{ overriddenCount }} 수정됨)</span>
      </button>

      <div class="tpl__spacer"></div>
      <!-- 무슨 값인지 말해 준다. 전에는 `com.poscodx.0eb8e37f.<boundedContext>` 가
           아무 설명 없이 떠 있어 읽는 사람이 뜻을 알 수 없었다. -->
      <span class="tpl__pkg">
        <span class="tpl__pkglabel">생성 패키지</span>
        com.poscodx.<b>{{ serviceId || 'serviceId' }}</b>.&lt;boundedContext&gt;
        <template v-if="!hasChoice">
          <span class="tpl__pkglabel">템플릿</span>{{ setName || '없음' }}
        </template>
      </span>
    </header>

    <p v-if="setsHint" class="tpl__banner tpl__banner--warn">
      {{ setsHint }} <span class="tpl__dim">{{ templatesRoot }}</span>
    </p>
    <p v-if="error" class="tpl__banner tpl__banner--err">{{ error }}</p>
    <!-- 템플릿을 고칠 수 있게 되면서 **문법 오류가 흔한 일**이 됐다. 첫 줄만
         보여 주면 어느 장이 왜 깨졌는지 알 수 없다 — 다 보여 준다. -->
    <div v-if="result?.errors?.length" class="tpl__banner tpl__banner--err">
      <b>템플릿 {{ result.errors.length }}건이 렌더링되지 않았습니다.</b>
      <span class="tpl__dim">수정모드에서 그 장을 열어 고치거나 원본으로 되돌리세요.</span>
      <ul class="tpl__errs">
        <li v-for="(e, i) in result.errors.slice(0, 8)" :key="i">
          <code>{{ e.template }}</code>
          <span v-if="e.item"> · {{ e.item }}</span> — {{ e.error }}
        </li>
      </ul>
      <span v-if="result.errors.length > 8" class="tpl__dim">
        그 밖에 {{ result.errors.length - 8 }}건 더
      </span>
    </div>

    <TemplateSourcePanel
      v-if="sourceMode"
      :set-name="setName"
      :files="templateFiles"
      @changed="onTemplateChanged"
    />

    <div v-else-if="result" class="tpl__body">
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
.tpl__btn--on { border-color: var(--ccw-accent); color: var(--ccw-accent); }

.tpl__spacer { flex: 1; }
.tpl__pkg {
  font-size: 11px; color: var(--ccw-text-dim); padding-bottom: 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.tpl__pkg b { color: var(--ccw-text-muted); font-weight: 600; }
.tpl__pkglabel {
  margin-right: 5px; padding: 0 5px; border-radius: 7px; font-size: 10px;
  color: var(--ccw-text-dim); border: 1px solid var(--ccw-border);
  font-family: inherit;
}
.tpl__pkglabel:not(:first-child) { margin-left: 10px; }
.tpl__errs { margin: 4px 0 0; padding-left: 18px; }
.tpl__errs li { margin: 1px 0; }
.tpl__errs code { color: var(--ccw-text-muted); }

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
