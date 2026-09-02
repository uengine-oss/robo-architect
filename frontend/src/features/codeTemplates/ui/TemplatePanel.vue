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
import { buildTree, collapseChains, firstFile } from '../tree.js'
import GeneratedTree from './GeneratedTree.vue'
import GeneratedViewer from './GeneratedViewer.vue'

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
const selected = ref(null)

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
  selected.value = null
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
    selected.value = firstFile(collapseChains(buildTree(result.value.files)))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}


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
        <GeneratedTree
          :files="result.files"
          :active-path="selected?.path || ''"
          @open="selected = $event"
        />
      </nav>
      <GeneratedViewer :file="selected" />
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
</style>
