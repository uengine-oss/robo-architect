<script setup>
/**
 * Template 탭 — 템플릿 기반 코드 생성.
 *
 * Code 탭(Claude Code TUI)과 별개다. 여기는 결정적 생성이다 — 같은 모델과
 * 같은 템플릿이면 같은 결과가 나온다.
 *
 * 렌더링을 브라우저에서 하는 이유는 템플릿이 자기 Handlebars 헬퍼를
 * JavaScript 로 들고 다니기 때문이다. 자세한 것은 `renderer.js` 주석.
 */
import { computed, onMounted, ref, watch } from 'vue'
import JSZip from 'jszip'
import { getContext, listFiles, listSessions, listSets } from '../api.js'
import { renderAll } from '../renderer.js'

const sets = ref([])
const setName = ref('')
const templatesRoot = ref('')
const setsHint = ref(null)

const sessions = ref([])
const sessionId = ref('')
const serviceId = ref('')
// 사용자가 손대기 전까지는 세션을 따라간다. 한 번 고치면 그 값을 지킨다.
const serviceIdEdited = ref(false)

const loading = ref(false)
const error = ref(null)
const result = ref(null)
const selectedPath = ref('')

const currentSession = computed(() => sessions.value.find((s) => s.id === sessionId.value))

/** 세션 이름에서 자바 패키지 한 마디로 쓸 만한 기본값을 만든다. */
function suggestServiceId(name) {
  const ascii = (name || '').replace(/[^0-9A-Za-z]+/g, '')
  return ascii ? ascii.charAt(0).toLowerCase() + ascii.slice(1) : ''
}

watch(sessionId, () => {
  if (serviceIdEdited.value) return
  serviceId.value = suggestServiceId(currentSession.value?.name) || sessionId.value
})

onMounted(async () => {
  try {
    const [s, d] = await Promise.all([listSets(), listSessions()])
    sets.value = s.sets || []
    templatesRoot.value = s.templatesRoot || ''
    setsHint.value = s.hint || null
    if (sets.value.length) setName.value = sets.value[0].name
    sessions.value = d.sessions || []
    if (sessions.value.length) sessionId.value = sessions.value[0].id
  } catch (e) {
    error.value = e.message
  }
})

async function generate() {
  error.value = null
  result.value = null
  selectedPath.value = ''
  if (!setName.value || !sessionId.value || !serviceId.value) {
    error.value = '템플릿 묶음·세션·Service ID 를 모두 지정하세요.'
    return
  }
  loading.value = true
  try {
    const [{ files: templates }, ctx] = await Promise.all([
      listFiles(setName.value),
      getContext(sessionId.value, serviceId.value),
    ])
    result.value = renderAll(templates, ctx)
    if (result.value.files.length) selectedPath.value = result.value.files[0].path
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const selectedFile = computed(
  () => (result.value?.files || []).find((f) => f.path === selectedPath.value) || null,
)

/** 파일 목록을 최상위 디렉터리(=BC)별로 묶어 보여 준다. */
const grouped = computed(() => {
  const out = new Map()
  for (const f of result.value?.files || []) {
    const key = f.path.split('/')[0]
    if (!out.has(key)) out.set(key, [])
    out.get(key).push(f)
  }
  return [...out.entries()].map(([name, files]) => ({ name, files }))
})

async function download() {
  if (!result.value?.files?.length) return
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
    <header class="tpl__bar">
      <label>
        <span>템플릿</span>
        <select v-model="setName" :disabled="!sets.length">
          <option v-for="s in sets" :key="s.name" :value="s.name">
            {{ s.name }} ({{ s.fileCount }})
          </option>
        </select>
      </label>

      <label>
        <span>세션</span>
        <select v-model="sessionId" :disabled="!sessions.length">
          <option v-for="s in sessions" :key="s.id" :value="s.id">
            {{ s.name }} — BC {{ s.boundedContexts }}
          </option>
        </select>
      </label>

      <label class="tpl__service">
        <span>Service ID</span>
        <input v-model="serviceId" placeholder="예: sample" @input="serviceIdEdited = true" />
      </label>

      <button class="tpl__go" :disabled="loading" @click="generate">
        {{ loading ? '생성 중…' : '코드 생성' }}
      </button>
      <button v-if="result?.files?.length" class="tpl__dl" @click="download">
        ZIP 내려받기 ({{ result.files.length }})
      </button>
    </header>

    <p class="tpl__note">
      패키지는 <code>com.poscodx.{{ serviceId || '&lt;serviceId&gt;' }}.&lt;boundedContext&gt;</code> 가 됩니다.
    </p>

    <p v-if="setsHint" class="tpl__warn">
      {{ setsHint }} <span class="tpl__dim">({{ templatesRoot }})</span>
    </p>
    <p v-if="error" class="tpl__err">{{ error }}</p>

    <p v-if="result?.errors?.length" class="tpl__warn">
      템플릿 {{ result.errors.length }}건이 렌더링되지 않았습니다.
      <span class="tpl__dim">{{ result.errors[0].template }} — {{ result.errors[0].error }}</span>
    </p>

    <div v-if="result" class="tpl__body">
      <nav class="tpl__tree">
        <div v-for="g in grouped" :key="g.name" class="tpl__group">
          <div class="tpl__group-name">{{ g.name }} <em>{{ g.files.length }}</em></div>
          <button
            v-for="f in g.files"
            :key="f.path"
            class="tpl__file"
            :class="{ 'is-active': f.path === selectedPath }"
            :title="f.path"
            @click="selectedPath = f.path"
          >
            {{ f.path.slice(g.name.length + 1) }}
          </button>
        </div>
      </nav>

      <section class="tpl__preview">
        <div v-if="selectedFile" class="tpl__preview-head">
          <code>{{ selectedFile.path }}</code>
          <span class="tpl__dim">{{ selectedFile.template }} · forEach {{ selectedFile.forEach }}</span>
        </div>
        <pre v-if="selectedFile"><code>{{ selectedFile.content }}</code></pre>
        <p v-else class="tpl__dim">왼쪽에서 파일을 고르세요.</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tpl { display: flex; flex-direction: column; height: 100%; padding: 12px 16px; gap: 8px; overflow: hidden; }
.tpl__bar { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
.tpl__bar label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.tpl__bar span { opacity: .7; }
.tpl__bar select, .tpl__bar input { padding: 5px 7px; font-size: 13px; min-width: 180px; }
.tpl__service input { min-width: 140px; }
.tpl__go, .tpl__dl { padding: 6px 14px; font-size: 13px; cursor: pointer; }
.tpl__go:disabled { cursor: default; opacity: .6; }
.tpl__note { font-size: 12px; opacity: .65; margin: 0; }
.tpl__err { color: #c0392b; font-size: 13px; margin: 0; }
.tpl__warn { color: #b8860b; font-size: 13px; margin: 0; }
.tpl__dim { opacity: .55; font-size: 12px; }
.tpl__body { display: grid; grid-template-columns: 340px 1fr; gap: 12px; flex: 1; min-height: 0; }
.tpl__tree { overflow: auto; border: 1px solid rgba(128,128,128,.25); border-radius: 4px; padding: 6px; }
.tpl__group { margin-bottom: 8px; }
.tpl__group-name { font-size: 12px; font-weight: 600; padding: 3px 4px; opacity: .8; }
.tpl__group-name em { opacity: .5; font-style: normal; font-weight: 400; }
.tpl__file { display: block; width: 100%; text-align: left; border: 0; background: none;
  font-size: 11px; padding: 2px 6px; cursor: pointer; color: inherit;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tpl__file:hover { background: rgba(128,128,128,.12); }
.tpl__file.is-active { background: rgba(66,133,244,.18); }
.tpl__preview { display: flex; flex-direction: column; min-height: 0;
  border: 1px solid rgba(128,128,128,.25); border-radius: 4px; }
.tpl__preview-head { display: flex; justify-content: space-between; gap: 12px;
  padding: 6px 10px; border-bottom: 1px solid rgba(128,128,128,.2); font-size: 12px; }
.tpl__preview pre { margin: 0; padding: 10px; overflow: auto; flex: 1;
  font-size: 12px; line-height: 1.45; }
</style>
