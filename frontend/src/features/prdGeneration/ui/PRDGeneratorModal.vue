<script setup>
import { ref, computed, onMounted, watch, inject } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close'])

const canvasStore = useCanvasStore()
const openClaudeCode = inject('openClaudeCode', null)

// Tech stack options (fetched from API)
const techStackOptions = ref({
  languages: [],
  frameworks: [],
  messaging: [],
  deployments: [],
  databases: [],
  frontend_frameworks: []
})

// Selected options
const config = ref({
  language: 'java',
  framework: 'spring-boot',
  messaging: 'kafka',
  deployment: 'microservices',
  database: 'postgresql',
  project_name: 'my-project',
  package_name: 'com.example',
  include_docker: true,
  include_kubernetes: false,
  include_tests: true,
  ai_assistant: 'cursor', // 'cursor' or 'claude'
  include_frontend: false,
  frontend_framework: null // 'vue', 'react', 'angular', etc.
})

// UI State
const isLoading = ref(false)
const isGenerating = ref(false)
const isSettingUp = ref(false)
const previewData = ref(null)
const error = ref(null)
const step = ref(1) // 1: Config, 2: Preview, 3: Download
const projectPath = ref('~/projects/')
const setupResult = ref(null)
const showFolderPicker = ref(false)
const folderPickerData = ref({ current_path: '', parent_path: null, directories: [] })
const isBrowsing = ref(false)

async function browseDirectory(path) {
  try {
    isBrowsing.value = true
    const response = await fetch(`/api/claude-code/browse-directory?path=${encodeURIComponent(path || '~')}`)
    if (response.ok) {
      folderPickerData.value = await response.json()
    }
  } catch (e) {
    console.error('Failed to browse directory:', e)
  } finally {
    isBrowsing.value = false
  }
}

function openFolderPicker() {
  showFolderPicker.value = true
  browseDirectory(projectPath.value)
}

function selectFolder(dirName) {
  const newPath = folderPickerData.value.current_path + '/' + dirName
  browseDirectory(newPath)
}

function goToParent() {
  if (folderPickerData.value.parent_path) {
    browseDirectory(folderPickerData.value.parent_path)
  }
}

function confirmFolderSelection() {
  projectPath.value = folderPickerData.value.current_path + '/'
  showFolderPicker.value = false
}

function createAndSelect() {
  // Use current browsed path + project name
  projectPath.value = folderPickerData.value.current_path + '/' + config.value.project_name
  showFolderPicker.value = false
}

const availableFrameworks = computed(() => {
  return techStackOptions.value.frameworks.filter(f => f.languages.includes(config.value.language))
})

watch(() => config.value.language, () => {
  const compatible = availableFrameworks.value.find(f => f.value === config.value.framework)
  if (!compatible && availableFrameworks.value.length > 0) {
    config.value.framework = availableFrameworks.value[0].value
  }
})

const messagingHint = computed(() => {
  if (config.value.deployment === 'modular-monolith') {
    return 'For modular monolith, "In-memory" uses internal event bus (e.g., AbstractAggregateRoot in Spring)'
  }
  return 'For microservices, external messaging platform is recommended for async communication'
})

onMounted(async () => {
  try {
    isLoading.value = true
    const response = await fetch('/api/prd/tech-stacks')
    if (response.ok) {
      const data = await response.json()
      techStackOptions.value = data
      // Ensure frontend_frameworks exists
      if (!techStackOptions.value.frontend_frameworks) {
        techStackOptions.value.frontend_frameworks = []
      }
      console.log('Tech stack options loaded:', techStackOptions.value)
    }
  } catch (e) {
    console.error('Failed to fetch tech stacks:', e)
  } finally {
    isLoading.value = false
  }
})

function getCanvasNodeIds() {
  // Return selected nodes if any, otherwise return all canvas nodes, or empty array for all BCs
  const selected = canvasStore.selectedNodes.length > 0 
    ? canvasStore.selectedNodes.map(n => n.id)
    : canvasStore.nodes.map(n => n.id)
  return selected.length > 0 ? selected : []
}

async function generatePreview() {
  const nodeIds = getCanvasNodeIds()
  // Allow empty nodeIds to generate PRD for all BCs

  try {
    isGenerating.value = true
    error.value = null

    const response = await fetch('/api/prd/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_ids: nodeIds.length > 0 ? nodeIds : null,
        tech_stack: config.value
      })
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to generate preview')
    }

    previewData.value = await response.json()
    step.value = 2
  } catch (e) {
    error.value = e.message
  } finally {
    isGenerating.value = false
  }
}

async function downloadZip() {
  const nodeIds = getCanvasNodeIds()

  try {
    isGenerating.value = true
    error.value = null

    const response = await fetch('/api/prd/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_ids: nodeIds.length > 0 ? nodeIds : null,
        tech_stack: config.value
      })
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to download')
    }

    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `${config.value.project_name}_prd.zip`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/)
      if (match) filename = match[1]
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    a.remove()

    step.value = 3
  } catch (e) {
    error.value = e.message
  } finally {
    isGenerating.value = false
  }
}

async function setupAndOpenClaudeCode() {
  const fullPath = projectPath.value.endsWith('/')
    ? projectPath.value + config.value.project_name
    : projectPath.value

  try {
    isSettingUp.value = true
    error.value = null

    const nodeIds = getCanvasNodeIds()
    const response = await fetch('/api/claude-code/setup-project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_path: fullPath,
        prd_request: {
          node_ids: nodeIds.length > 0 ? nodeIds : null,
          tech_stack: config.value
        }
      })
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || 'Failed to setup project')
    }

    setupResult.value = await response.json()
    step.value = 4
  } catch (e) {
    error.value = e.message
  } finally {
    isSettingUp.value = false
  }
}

function openInClaudeCode() {
  if (setupResult.value && openClaudeCode) {
    openClaudeCode(setupResult.value.project_path)
    closeModal()
  }
}

function closeModal() {
  step.value = 1
  previewData.value = null
  setupResult.value = null
  error.value = null
  emit('close')
}

function goBack() {
  if (step.value > 1) {
    step.value--
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="closeModal">
      <div class="modal-container">
        <div class="modal-header">
          <div class="header-content">
            <svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            <div>
              <h2>Generate PRD for Vibe Coding</h2>
              <p class="header-subtitle">Create AI-ready project specs from your Event Storming model</p>
            </div>
          </div>
          <button class="close-btn" @click="closeModal">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div class="step-indicator">
          <div class="step" :class="{ active: step >= 1, completed: step > 1 }">
            <div class="step-number">1</div>
            <span>Configure</span>
          </div>
          <div class="step-line" :class="{ active: step > 1 }"></div>
          <div class="step" :class="{ active: step >= 2, completed: step > 2 }">
            <div class="step-number">2</div>
            <span>Preview</span>
          </div>
          <div class="step-line" :class="{ active: step > 2 }"></div>
          <div class="step" :class="{ active: step >= 3, completed: step === 3 }">
            <div class="step-number">3</div>
            <span>Download</span>
          </div>
        </div>

        <div class="modal-content">
          <div v-if="error" class="error-alert">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{{ error }}</span>
            <button @click="error = null">×</button>
          </div>

          <div v-if="step === 1" class="config-step">
            <div class="config-section">
              <h3>📦 Project Information</h3>
              <div class="form-grid">
                <div class="form-group">
                  <label>Project Name</label>
                  <input v-model="config.project_name" type="text" placeholder="my-project" class="form-input" />
                </div>
                <div class="form-group">
                  <label>Package Name (Java/Kotlin)</label>
                  <input v-model="config.package_name" type="text" placeholder="com.example" class="form-input" />
                </div>
              </div>
            </div>

            <div class="config-section">
              <h3>🛠️ Technology Stack</h3>
              <div class="form-grid">
                <div class="form-group">
                  <label>Language</label>
                  <select v-model="config.language" class="form-select">
                    <option v-for="lang in techStackOptions.languages" :key="lang.value" :value="lang.value">
                      {{ lang.label }}
                    </option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Framework</label>
                  <select v-model="config.framework" class="form-select">
                    <option v-for="fw in availableFrameworks" :key="fw.value" :value="fw.value">
                      {{ fw.label }}
                    </option>
                  </select>
                </div>
              </div>
            </div>

            <div class="config-section">
              <h3>🚀 Architecture</h3>
              <div class="form-grid">
                <div class="form-group">
                  <label>Deployment Style</label>
                  <div class="radio-cards">
                    <label class="radio-card" :class="{ selected: config.deployment === 'microservices' }">
                      <input type="radio" v-model="config.deployment" value="microservices" />
                      <div class="radio-card-content">
                        <span class="radio-icon">🔀</span>
                        <span class="radio-label">Microservices</span>
                        <span class="radio-desc">Separate deployable services</span>
                      </div>
                    </label>
                    <label class="radio-card" :class="{ selected: config.deployment === 'modular-monolith' }">
                      <input type="radio" v-model="config.deployment" value="modular-monolith" />
                      <div class="radio-card-content">
                        <span class="radio-icon">📦</span>
                        <span class="radio-label">Modular Monolith</span>
                        <span class="radio-desc">Single app, modular design</span>
                      </div>
                    </label>
                  </div>
                </div>
              </div>

              <div class="form-grid">
                <div class="form-group">
                  <label>Messaging Platform</label>
                  <select v-model="config.messaging" class="form-select">
                    <option v-for="msg in techStackOptions.messaging" :key="msg.value" :value="msg.value">
                      {{ msg.label }}
                    </option>
                  </select>
                  <p class="form-hint">{{ messagingHint }}</p>
                </div>
                <div class="form-group">
                  <label>Database</label>
                  <select v-model="config.database" class="form-select">
                    <option v-for="db in techStackOptions.databases" :key="db.value" :value="db.value">
                      {{ db.label }}
                    </option>
                  </select>
                </div>
              </div>
            </div>

            <div class="config-section">
              <h3>🎨 Frontend</h3>
              <div class="form-group">
                <label>
                  <input type="checkbox" v-model="config.include_frontend" />
                  Include Frontend PRD and Rules
                </label>
                <p class="form-hint">Generate Frontend-PRD.md and frontend framework-specific Cursor rules</p>
              </div>
              <div v-if="config.include_frontend" class="form-group" style="margin-top: 12px;">
                <label>Frontend Framework</label>
                <select v-model="config.frontend_framework" class="form-select">
                  <option :value="null">Select framework...</option>
                  <option v-for="fw in techStackOptions.frontend_frameworks" :key="fw.value" :value="fw.value">
                    {{ fw.label }}
                  </option>
                </select>
                <p v-if="techStackOptions.frontend_frameworks.length === 0" class="form-hint" style="color: #f59e0b;">
                  No frontend frameworks available. Please refresh the page.
                </p>
                <p v-else class="form-hint">Select frontend framework for UI implementation guidelines</p>
              </div>
            </div>

            <div class="config-section">
              <h3>🤖 AI Assistant</h3>
              <div class="form-group">
                <label>Choose AI Assistant</label>
                <div class="radio-cards">
                  <label class="radio-card" :class="{ selected: config.ai_assistant === 'cursor' }">
                    <input type="radio" v-model="config.ai_assistant" value="cursor" />
                    <div class="radio-card-content">
                      <span class="radio-icon">🎯</span>
                      <span class="radio-label">Cursor</span>
                      <span class="radio-desc">Cursor IDE rules</span>
                    </div>
                  </label>
                  <label class="radio-card" :class="{ selected: config.ai_assistant === 'claude' }">
                    <input type="radio" v-model="config.ai_assistant" value="claude" />
                    <div class="radio-card-content">
                      <span class="radio-icon">🤖</span>
                      <span class="radio-label">Claude</span>
                      <span class="radio-desc">Claude Code agents (will be improved later)</span>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            <div class="config-section">
              <h3>⚙️ Additional Options</h3>
              <div class="checkbox-group">
                <label class="checkbox-item">
                  <input type="checkbox" v-model="config.include_docker" />
                  <span class="checkbox-label">Include Docker Configuration</span>
                </label>
                <label class="checkbox-item">
                  <input type="checkbox" v-model="config.include_kubernetes" />
                  <span class="checkbox-label">Include Kubernetes Manifests</span>
                </label>
                <label class="checkbox-item">
                  <input type="checkbox" v-model="config.include_tests" />
                  <span class="checkbox-label">Include Test Templates</span>
                </label>
              </div>
            </div>
          </div>

          <div v-if="step === 2 && previewData" class="preview-step">
            <div class="preview-section">
              <h3>📋 Bounded Contexts</h3>
              <div class="bc-list">
                <div v-for="bc in previewData.bounded_contexts" :key="bc.id" class="bc-item">
                  <span class="bc-icon">📦</span>
                  <span class="bc-name">{{ bc.name }}</span>
                </div>
              </div>
            </div>

            <div class="preview-section">
              <h3>📂 Files to Generate</h3>
              <div class="file-tree">
                <div v-for="file in previewData.files_to_generate" :key="file" class="file-item">
                  <span class="file-icon">
                    {{ file.endsWith('.md') ? '📄' : file.endsWith('.yml') || file.endsWith('.yaml') ? '⚙️' : '📋' }}
                  </span>
                  <span class="file-name">{{ file }}</span>
                </div>
              </div>
            </div>

            <div class="preview-section">
              <h3>🛠️ Tech Stack Summary</h3>
              <div class="tech-summary">
                <div class="tech-item"><span class="tech-label">Language:</span><span class="tech-value">{{ previewData.tech_stack.language }}</span></div>
                <div class="tech-item"><span class="tech-label">Framework:</span><span class="tech-value">{{ previewData.tech_stack.framework }}</span></div>
                <div v-if="previewData.tech_stack.include_frontend && previewData.tech_stack.frontend_framework" class="tech-item">
                  <span class="tech-label">Frontend:</span><span class="tech-value">{{ previewData.tech_stack.frontend_framework }}</span>
                </div>
                <div class="tech-item"><span class="tech-label">Messaging:</span><span class="tech-value">{{ previewData.tech_stack.messaging }}</span></div>
                <div class="tech-item"><span class="tech-label">Deployment:</span><span class="tech-value">{{ previewData.tech_stack.deployment }}</span></div>
                <div class="tech-item"><span class="tech-label">AI Assistant:</span><span class="tech-value">{{ previewData.tech_stack.ai_assistant === 'cursor' ? 'Cursor' : 'Claude Code' }}</span></div>
              </div>
            </div>
          </div>

          <div v-if="step === 3" class="complete-step">
            <div class="complete-icon">✅</div>
            <h3>Download Complete!</h3>
            <p>Your PRD package has been downloaded.</p>

            <div class="claude-code-setup">
              <div class="setup-divider">
                <span>or</span>
              </div>
              <h4>Claude Code에서 바로 열기</h4>
              <p class="setup-desc">PRD 파일을 지정한 경로에 추출하고 Claude Code 터미널을 엽니다.</p>
              <div class="setup-path-group">
                <label>프로젝트 경로</label>
                <div class="setup-path-input">
                  <input
                    v-model="projectPath"
                    type="text"
                    :placeholder="`~/projects/${config.project_name}`"
                    class="form-input"
                  />
                  <button class="btn-browse" @click.stop="openFolderPicker" title="폴더 탐색">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    </svg>
                  </button>
                </div>
                <p class="form-hint">경로가 <code>/</code>로 끝나면 프로젝트 이름(<code>{{ config.project_name }}</code>)이 자동 추가됩니다.</p>
              </div>

              <!-- Folder Picker Overlay -->
              <Teleport to="body">
                <div v-if="showFolderPicker" class="folder-picker-overlay" @click.self="showFolderPicker = false">
                  <div class="folder-picker">
                    <div class="folder-picker__header">
                      <h4>폴더 선택</h4>
                      <button class="folder-picker__close" @click="showFolderPicker = false">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </button>
                    </div>
                    <div class="folder-picker__nav">
                      <button
                        class="folder-picker__up"
                        :disabled="!folderPickerData.parent_path"
                        @click="goToParent"
                        title="상위 폴더"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="15 18 9 12 15 6"></polyline>
                        </svg>
                      </button>
                      <span class="folder-picker__path">{{ folderPickerData.current_path }}</span>
                    </div>
                    <div class="folder-picker__list">
                      <div v-if="isBrowsing" class="folder-picker__loading">탐색 중...</div>
                      <div v-else-if="folderPickerData.directories.length === 0" class="folder-picker__empty">하위 폴더 없음</div>
                      <button
                        v-for="dir in folderPickerData.directories"
                        :key="dir"
                        class="folder-picker__item"
                        @click="selectFolder(dir)"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span>{{ dir }}</span>
                      </button>
                    </div>
                    <div class="folder-picker__actions">
                      <button class="btn-sm btn-ghost" @click="showFolderPicker = false">취소</button>
                      <button class="btn-sm btn-ghost" @click="createAndSelect">
                        여기에 <code>{{ config.project_name }}</code> 생성
                      </button>
                      <button class="btn-sm btn-accent" @click="confirmFolderSelection">이 폴더 선택</button>
                    </div>
                  </div>
                </div>
              </Teleport>
              <button
                class="btn btn-claude"
                @click="setupAndOpenClaudeCode"
                :disabled="isSettingUp || !projectPath"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="4 17 10 11 4 5"></polyline>
                  <line x1="12" y1="19" x2="20" y2="19"></line>
                </svg>
                <span v-if="isSettingUp">프로젝트 설정 중...</span>
                <span v-else>Claude Code에서 열기</span>
              </button>
            </div>

            <div class="next-steps">
              <h4>수동 설정 가이드:</h4>
              <ol>
                <li>Extract the ZIP file</li>
                <li v-if="config.ai_assistant === 'cursor'">
                  Open the project in <strong>Cursor IDE</strong>
                  <ul style="margin-top: 4px; padding-left: 20px;">
                    <li>Review <code>PRD.md</code> for overall architecture</li>
                    <li v-if="config.include_frontend && config.frontend_framework">Review <code>Frontend-PRD.md</code> for frontend requirements</li>
                    <li>Check <code>specs/</code> folder for BC-specific specifications</li>
                    <li>Backend rules: <code>.cursor/rules/{{ config.framework }}.mdc</code></li>
                    <li v-if="config.include_frontend && config.frontend_framework">Frontend rules: <code>.cursor/rules/{{ config.frontend_framework }}.mdc</code></li>
                    <li>Global rules are in <code>.cursorrules</code></li>
                  </ul>
                </li>
                <li v-else>
                  Use with <strong>Claude Code</strong>
                  <ul style="margin-top: 4px; padding-left: 20px;">
                    <li>BC-specific agents are in <code>.claude/agents/*.md</code></li>
                    <li>Read <code>CLAUDE.md</code> for project context</li>
                  </ul>
                </li>
                <li>Check <code>specs/</code> folder for BC-specific specifications</li>
                <li>Read <code>PRD.md</code> for architecture guidelines</li>
              </ol>
            </div>
          </div>

          <!-- Step 4: Setup complete, open Claude Code -->
          <div v-if="step === 4 && setupResult" class="complete-step">
            <div class="complete-icon">🚀</div>
            <h3>프로젝트 설정 완료!</h3>
            <p class="setup-path-result">
              <code>{{ setupResult.project_path }}</code>
            </p>
            <p>{{ setupResult.files_extracted.length }}개 파일이 추출되었습니다.</p>

            <div class="extracted-files">
              <div v-for="file in setupResult.files_extracted" :key="file" class="file-item">
                <span class="file-icon">
                  {{ file.endsWith('.md') ? '📄' : file.endsWith('.yml') || file.endsWith('.yaml') ? '⚙️' : '📋' }}
                </span>
                <span class="file-name">{{ file }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button v-if="step > 1 && step < 3" class="btn btn-secondary" @click="goBack">← Back</button>
          <div class="footer-spacer"></div>
          <button v-if="step === 1" class="btn btn-primary" @click="generatePreview" :disabled="isGenerating">
            <span v-if="isGenerating">Generating...</span>
            <span v-else>Preview →</span>
          </button>
          <button v-if="step === 2" class="btn btn-primary" @click="downloadZip" :disabled="isGenerating">
            <span v-if="isGenerating">Downloading...</span>
            <span v-else>Download ZIP 📥</span>
          </button>
          <button v-if="step === 3" class="btn btn-primary" @click="closeModal">Done</button>
          <button v-if="step === 4" class="btn btn-claude" @click="openInClaudeCode">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="4 17 10 11 4 5"></polyline>
              <line x1="12" y1="19" x2="20" y2="19"></line>
            </svg>
            Claude Code 터미널 열기
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-container {
  background: #1a1b26;
  border-radius: 16px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid #3d4154;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 24px;
  border-bottom: 1px solid #3d4154;
  background: linear-gradient(135deg, #1a1b26 0%, #24283b 100%);
}

.header-content {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.header-icon {
  width: 40px;
  height: 40px;
  color: #7aa2f7;
  flex-shrink: 0;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #c0caf5;
  font-weight: 600;
}

.header-subtitle {
  margin: 4px 0 0;
  color: #787c99;
  font-size: 0.875rem;
}

.close-btn {
  background: none;
  border: none;
  color: #787c99;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #3d4154;
  color: #c0caf5;
}

.close-btn svg {
  width: 20px;
  height: 20px;
}

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  gap: 12px;
  background: #16161e;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #565a72;
  transition: color 0.3s;
}

.step.active { color: #7aa2f7; }
.step.completed { color: #9ece6a; }

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #3d4154;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
  transition: all 0.3s;
}

.step.active .step-number { background: #7aa2f7; color: #1a1b26; }
.step.completed .step-number { background: #9ece6a; color: #1a1b26; }

.step-line {
  width: 60px;
  height: 2px;
  background: #3d4154;
  transition: background 0.3s;
}

.step-line.active { background: #7aa2f7; }

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.error-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(247, 118, 142, 0.15);
  border: 1px solid #f7768e;
  border-radius: 8px;
  margin-bottom: 20px;
  color: #f7768e;
}

.error-alert svg { width: 20px; height: 20px; flex-shrink: 0; }
.error-alert span { flex: 1; }
.error-alert button { background: none; border: none; color: #f7768e; font-size: 1.25rem; cursor: pointer; padding: 0; }

.config-section { margin-bottom: 28px; }
.config-section h3 { margin: 0 0 16px; font-size: 1rem; color: #c0caf5; font-weight: 600; }

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 0.875rem; color: #a9b1d6; font-weight: 500; }

.form-input,
.form-select {
  padding: 10px 12px;
  background: #24283b;
  border: 1px solid #3d4154;
  border-radius: 8px;
  color: #c0caf5;
  font-size: 0.9rem;
  transition: border-color 0.2s;
}

.form-input:focus,
.form-select:focus { outline: none; border-color: #7aa2f7; }
.form-select { cursor: pointer; }

.form-hint { margin: 4px 0 0; font-size: 0.75rem; color: #787c99; line-height: 1.4; }

.radio-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.radio-card { position: relative; cursor: pointer; }
.radio-card input { position: absolute; opacity: 0; }
.radio-card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  background: #24283b;
  border: 2px solid #3d4154;
  border-radius: 12px;
  transition: all 0.2s;
}

.radio-card.selected .radio-card-content { border-color: #7aa2f7; background: rgba(122, 162, 247, 0.1); }
.radio-icon { font-size: 1.5rem; margin-bottom: 8px; }
.radio-label { font-weight: 600; color: #c0caf5; margin-bottom: 4px; }
.radio-desc { font-size: 0.75rem; color: #787c99; text-align: center; }

.checkbox-group { display: flex; flex-direction: column; gap: 12px; }
.checkbox-item { display: flex; align-items: center; gap: 12px; cursor: pointer; }
.checkbox-item input { width: 18px; height: 18px; accent-color: #7aa2f7; }
.checkbox-label { color: #a9b1d6; font-size: 0.9rem; }

.preview-section { margin-bottom: 24px; }
.preview-section h3 { margin: 0 0 12px; font-size: 1rem; color: #c0caf5; font-weight: 600; }
.bc-list { display: flex; flex-wrap: wrap; gap: 8px; }
.bc-item { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #24283b; border-radius: 8px; color: #a9b1d6; }

.file-tree { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #24283b; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #9ece6a; }

.tech-summary { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.tech-item { display: flex; gap: 8px; padding: 8px 12px; background: #24283b; border-radius: 6px; }
.tech-label { color: #787c99; }
.tech-value { color: #7aa2f7; font-weight: 500; }

.complete-step { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 40px 20px; }
.complete-icon { font-size: 4rem; margin-bottom: 16px; }
.complete-step h3 { margin: 0 0 8px; font-size: 1.5rem; color: #9ece6a; }
.complete-step p { color: #a9b1d6; margin-bottom: 32px; }

.next-steps { text-align: left; background: #24283b; padding: 20px 24px; border-radius: 12px; width: 100%; max-width: 500px; }
.next-steps h4 { margin: 0 0 12px; color: #c0caf5; }
.next-steps ol { margin: 0; padding-left: 20px; color: #a9b1d6; }
.next-steps li { margin-bottom: 8px; line-height: 1.5; }
.next-steps code { background: #16161e; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.85em; color: #7aa2f7; }

.modal-footer { display: flex; align-items: center; padding: 16px 24px; border-top: 1px solid #3d4154; background: #16161e; }
.footer-spacer { flex: 1; }
.btn { padding: 10px 24px; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; }
.btn-primary { background: linear-gradient(135deg, #7aa2f7, #5d8ffc); color: white; }
.btn-primary:hover:not(:disabled) { background: linear-gradient(135deg, #8aafff, #6d9aff); transform: translateY(-1px); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #3d4154; color: #a9b1d6; }
.btn-secondary:hover { background: #4a4f66; }
.btn-claude {
  background: linear-gradient(135deg, #bb9af7, #7c3aed);
  color: white;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-claude:hover:not(:disabled) { background: linear-gradient(135deg, #c9abff, #8b4cf6); transform: translateY(-1px); }
.btn-claude:disabled { opacity: 0.6; cursor: not-allowed; }

.claude-code-setup {
  width: 100%;
  max-width: 500px;
  margin-bottom: 24px;
}

.setup-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px 0 16px;
  color: #565a72;
  font-size: 0.8rem;
}

.setup-divider::before,
.setup-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #3d4154;
}

.setup-desc {
  color: #787c99;
  font-size: 0.8rem;
  margin: 4px 0 16px;
}

.setup-path-group {
  margin-bottom: 16px;
  text-align: left;
}

.setup-path-group label {
  font-size: 0.8rem;
  color: #a9b1d6;
  font-weight: 500;
  display: block;
  margin-bottom: 6px;
}

.setup-path-input {
  display: flex;
  gap: 8px;
}

.setup-path-input .form-input {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}

.setup-path-result {
  margin-bottom: 8px;
}

.setup-path-result code {
  background: #16161e;
  padding: 4px 10px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85em;
  color: #9ece6a;
}

.extracted-files {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  width: 100%;
  max-width: 500px;
  margin-top: 16px;
  max-height: 200px;
  overflow-y: auto;
}

/* Browse button */
.btn-browse {
  padding: 10px 12px;
  background: #3d4154;
  border: 1px solid #565a72;
  border-radius: 8px;
  color: #a9b1d6;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.btn-browse:hover {
  background: #4a4f66;
  border-color: #7aa2f7;
  color: #7aa2f7;
}

/* Folder Picker styles moved to unscoped <style> block below (Teleport to body) */

.btn-sm {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.7rem;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.btn-sm code { font-size: 0.7rem; background: none; padding: 0; color: inherit; }
.btn-ghost { background: none; color: #787c99; }
.btn-ghost:hover { color: #a9b1d6; background: #3d4154; }
.btn-accent { background: #7aa2f7; color: #1a1b26; font-weight: 600; }
.btn-accent:hover { background: #8aafff; }

@media (max-width: 640px) {
  .form-grid, .radio-cards, .file-tree, .tech-summary { grid-template-columns: 1fr; }
  .step-indicator { padding: 16px; gap: 8px; }
  .step-line { width: 30px; }
  .step span { display: none; }
}
</style>

<!-- Unscoped styles for Teleport'd folder picker -->
<style>
.folder-picker-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.folder-picker {
  background: #1a1b26;
  border: 1px solid #3d4154;
  border-radius: 12px;
  width: 500px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.5);
}

.folder-picker__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 12px;
}

.folder-picker__header h4 {
  margin: 0;
  color: #c0caf5;
  font-size: 1rem;
}

.folder-picker__close {
  background: none;
  border: none;
  color: #565a72;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
}
.folder-picker__close:hover { color: #c0caf5; background: #3d4154; }

.folder-picker__nav {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px 12px;
  border-bottom: 1px solid #3d4154;
}

.folder-picker__up {
  background: none;
  border: 1px solid #3d4154;
  border-radius: 4px;
  color: #a9b1d6;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}
.folder-picker__up:hover:not(:disabled) { background: #3d4154; color: #7aa2f7; }
.folder-picker__up:disabled { opacity: 0.3; cursor: not-allowed; }

.folder-picker__path {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #7aa2f7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-picker__list {
  max-height: 300px;
  overflow-y: auto;
  padding: 4px 8px;
}

.folder-picker__loading,
.folder-picker__empty {
  padding: 16px;
  text-align: center;
  color: #565a72;
  font-size: 0.8rem;
}

.folder-picker__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 10px;
  background: none;
  border: none;
  border-radius: 4px;
  color: #a9b1d6;
  font-size: 0.8rem;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.folder-picker__item:hover {
  background: rgba(122, 162, 247, 0.1);
  color: #c0caf5;
}
.folder-picker__item svg { color: #e0af68; flex-shrink: 0; }

.folder-picker__actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  padding: 8px 12px;
  border-top: 1px solid #3d4154;
  background: #16161e;
  border-radius: 0 0 12px 12px;
}

.folder-picker .btn-sm {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.7rem;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.folder-picker .btn-sm code { font-size: 0.7rem; background: none; padding: 0; color: inherit; }
.folder-picker .btn-ghost { background: none; color: #787c99; }
.folder-picker .btn-ghost:hover { color: #a9b1d6; background: #3d4154; }
.folder-picker .btn-accent { background: #7aa2f7; color: #1a1b26; font-weight: 600; }
.folder-picker .btn-accent:hover { background: #8aafff; }
</style>


