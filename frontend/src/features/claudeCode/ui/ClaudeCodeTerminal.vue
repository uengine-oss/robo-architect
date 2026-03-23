<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch, inject } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'

const props = defineProps({
  workdir: {
    type: String,
    default: ''
  }
})

const terminalRef = ref(null)
let terminal = null
let fitAddon = null
let ws = null
let resizeObserver = null
let currentWorkdir = ''

const isConnected = ref(false)
const isConnecting = ref(true)
const connectionError = ref('')
const workdirDisplay = ref('')

// Write batching — collect incoming data and flush via requestAnimationFrame
// to avoid excessive xterm.js render cycles during heavy output.
let writeBuf = ''
let writeRaf = null

function flushTerminalWrites() {
  writeRaf = null
  if (writeBuf && terminal) {
    terminal.write(writeBuf)
    writeBuf = ''
  }
}

function queueTerminalWrite(data) {
  writeBuf += data
  if (!writeRaf) {
    writeRaf = requestAnimationFrame(flushTerminalWrites)
  }
}

// Folder picker state
const showFolderPicker = ref(false)
const folderPickerData = ref({ current_path: '', parent_path: null, directories: [] })
const isBrowsing = ref(false)

async function browseDirectory(path) {
  try {
    isBrowsing.value = true
    const host = import.meta.env.VITE_API_HOST || window.location.hostname
    const port = import.meta.env.VITE_API_PORT || '8000'
    const response = await fetch(`http://${host}:${port}/api/claude-code/browse-directory?path=${encodeURIComponent(path || '~')}`)
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
  browseDirectory(currentWorkdir || '~')
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
  const selectedPath = folderPickerData.value.current_path
  showFolderPicker.value = false
  if (terminal) {
    terminal.clear()
  }
  connect(selectedPath)
}

function getWsUrl(workdir) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = import.meta.env.VITE_API_HOST || window.location.hostname
  const port = import.meta.env.VITE_API_PORT || '8000'
  let url = `${protocol}//${host}:${port}/api/claude-code/terminal`
  if (workdir) {
    url += `?workdir=${encodeURIComponent(workdir)}`
  }
  return url
}

function createTerminal() {
  terminal = new Terminal({
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 14,
    fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", Menlo, Monaco, "Courier New", monospace',
    theme: {
      background: '#1a1b26',
      foreground: '#c0caf5',
      cursor: '#c0caf5',
      cursorAccent: '#1a1b26',
      selectionBackground: 'rgba(82, 139, 255, 0.3)',
      black: '#15161e',
      red: '#f7768e',
      green: '#9ece6a',
      yellow: '#e0af68',
      blue: '#7aa2f7',
      magenta: '#bb9af7',
      cyan: '#7dcfff',
      white: '#a9b1d6',
      brightBlack: '#414868',
      brightRed: '#f7768e',
      brightGreen: '#9ece6a',
      brightYellow: '#e0af68',
      brightBlue: '#7aa2f7',
      brightMagenta: '#bb9af7',
      brightCyan: '#7dcfff',
      brightWhite: '#c0caf5',
    },
    allowProposedApi: true,
    scrollback: 5000,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.loadAddon(new WebLinksAddon())
}

function connect(workdir) {
  // Close existing connection
  if (ws) {
    ws.close()
  }

  isConnecting.value = true
  connectionError.value = ''
  currentWorkdir = workdir || ''
  workdirDisplay.value = currentWorkdir

  const url = getWsUrl(currentWorkdir)
  ws = new WebSocket(url)

  ws.onopen = () => {
    isConnected.value = true
    isConnecting.value = false
    connectionError.value = ''

    // Send initial terminal size
    const dims = { cols: terminal.cols, rows: terminal.rows }
    ws.send(JSON.stringify({ type: 'resize', ...dims }))
  }

  ws.onmessage = (event) => {
    if (terminal) {
      queueTerminalWrite(event.data)
    }
  }

  ws.onclose = (event) => {
    isConnected.value = false
    isConnecting.value = false
    if (terminal && !event.wasClean) {
      terminal.write('\r\n\x1b[31m[연결 종료]\x1b[0m\r\n')
    }
  }

  ws.onerror = () => {
    isConnected.value = false
    isConnecting.value = false
    connectionError.value = '백엔드 터미널 서비스에 연결할 수 없습니다.'
  }
}

function handleResize() {
  if (!fitAddon || !terminal) return
  try {
    fitAddon.fit()
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'resize',
        cols: terminal.cols,
        rows: terminal.rows,
      }))
    }
  } catch {}
}

function reconnect() {
  if (terminal) {
    terminal.clear()
  }
  connect(currentWorkdir)
}

// Expose openWithWorkdir for parent to call
function openWithWorkdir(workdir) {
  if (terminal) {
    terminal.clear()
  }
  connect(workdir)
}

defineExpose({ openWithWorkdir })

// Watch for workdir prop changes
watch(() => props.workdir, (newWorkdir) => {
  if (newWorkdir && newWorkdir !== currentWorkdir) {
    openWithWorkdir(newWorkdir)
  }
})

onMounted(async () => {
  await nextTick()

  createTerminal()
  terminal.open(terminalRef.value)

  // Handle user input → send to backend
  terminal.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }))
    }
  })

  // Fit terminal to container
  fitAddon.fit()

  // Watch for container resize
  resizeObserver = new ResizeObserver(() => {
    handleResize()
  })
  resizeObserver.observe(terminalRef.value)

  // Connect to backend
  connect(props.workdir)
})

onUnmounted(() => {
  if (writeRaf) {
    cancelAnimationFrame(writeRaf)
    writeRaf = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (ws) {
    ws.close()
  }
  if (terminal) {
    terminal.dispose()
  }
})
</script>

<template>
  <div class="claude-code-terminal">
    <!-- Header bar -->
    <div class="terminal-header">
      <div class="terminal-header__left">
        <div class="terminal-header__title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="4 17 10 11 4 5"></polyline>
            <line x1="12" y1="19" x2="20" y2="19"></line>
          </svg>
          <span>Claude Code</span>
        </div>
        <button
          class="terminal-header__workdir"
          :title="workdirDisplay ? workdirDisplay + ' (클릭하여 경로 변경)' : '작업 경로 선택'"
          @click="openFolderPicker"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span>{{ workdirDisplay || '경로 선택...' }}</span>
          <svg class="workdir-edit-icon" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <div class="terminal-header__status">
          <span
            class="status-dot"
            :class="{ 'is-connected': isConnected, 'is-connecting': isConnecting, 'is-error': connectionError }"
          ></span>
          <span class="status-text">
            {{ isConnecting ? '연결 중...' : isConnected ? '연결됨' : '연결 끊김' }}
          </span>
        </div>
      </div>
      <div class="terminal-header__right">
        <button
          v-if="!isConnected && !isConnecting"
          class="reconnect-btn"
          @click="reconnect"
          title="재연결"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          <span>재연결</span>
        </button>
      </div>
    </div>

    <!-- Connection error overlay -->
    <div v-if="connectionError && !isConnected" class="terminal-error-overlay">
      <div class="terminal-error-content">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <p>{{ connectionError }}</p>
        <button class="error-reconnect-btn" @click="reconnect">재연결</button>
      </div>
    </div>

    <!-- Terminal container -->
    <div ref="terminalRef" class="terminal-container"></div>

    <!-- Folder picker overlay -->
    <Teleport to="body">
      <div v-if="showFolderPicker" class="tcc-folder-overlay" @click.self="showFolderPicker = false">
        <div class="tcc-folder-picker">
          <div class="tcc-folder-picker__header">
            <h4>작업 경로 변경</h4>
            <button class="tcc-folder-picker__close" @click="showFolderPicker = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="tcc-folder-picker__nav">
            <button
              class="tcc-folder-picker__up"
              :disabled="!folderPickerData.parent_path"
              @click="goToParent"
              title="상위 폴더"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 18 9 12 15 6"></polyline>
              </svg>
            </button>
            <span class="tcc-folder-picker__path">{{ folderPickerData.current_path }}</span>
          </div>
          <div class="tcc-folder-picker__list">
            <div v-if="isBrowsing" class="tcc-folder-picker__loading">탐색 중...</div>
            <div v-else-if="folderPickerData.directories.length === 0" class="tcc-folder-picker__empty">하위 폴더 없음</div>
            <button
              v-for="dir in folderPickerData.directories"
              :key="dir"
              class="tcc-folder-picker__item"
              @click="selectFolder(dir)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span>{{ dir }}</span>
            </button>
          </div>
          <div class="tcc-folder-picker__actions">
            <button class="tcc-btn-ghost" @click="showFolderPicker = false">취소</button>
            <button class="tcc-btn-accent" @click="confirmFolderSelection">이 폴더에서 열기</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.claude-code-terminal {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #1a1b26;
  position: relative;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #16161e;
  border-bottom: 1px solid #292e42;
  flex-shrink: 0;
}

.terminal-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.terminal-header__title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #c0caf5;
  font-size: 0.8rem;
  font-weight: 600;
}

.terminal-header__title svg {
  color: #bb9af7;
}

.terminal-header__workdir {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: rgba(122, 162, 247, 0.1);
  border: 1px solid rgba(122, 162, 247, 0.2);
  border-radius: 4px;
  color: #7aa2f7;
  font-size: 0.65rem;
  font-family: 'JetBrains Mono', monospace;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s;
}

.terminal-header__workdir:hover {
  background: rgba(122, 162, 247, 0.2);
  border-color: rgba(122, 162, 247, 0.4);
}

.workdir-edit-icon {
  opacity: 0.4;
  flex-shrink: 0;
  transition: opacity 0.15s;
}

.terminal-header__workdir:hover .workdir-edit-icon {
  opacity: 1;
}

.terminal-header__status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #414868;
}

.status-dot.is-connected {
  background: #9ece6a;
  box-shadow: 0 0 6px rgba(158, 206, 106, 0.5);
}

.status-dot.is-connecting {
  background: #e0af68;
  animation: pulse 1.5s infinite;
}

.status-dot.is-error {
  background: #f7768e;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-text {
  font-size: 0.7rem;
  color: #565f89;
}

.terminal-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reconnect-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(187, 154, 247, 0.15);
  border: 1px solid rgba(187, 154, 247, 0.3);
  border-radius: 4px;
  color: #bb9af7;
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
}

.reconnect-btn:hover {
  background: rgba(187, 154, 247, 0.25);
  border-color: #bb9af7;
}

.terminal-error-overlay {
  position: absolute;
  top: 44px;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(26, 27, 38, 0.9);
  z-index: 10;
}

.terminal-error-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #565f89;
}

.terminal-error-content svg {
  color: #f7768e;
}

.terminal-error-content p {
  font-size: 0.8rem;
  margin: 0;
}

.error-reconnect-btn {
  padding: 6px 16px;
  background: rgba(187, 154, 247, 0.2);
  border: 1px solid rgba(187, 154, 247, 0.4);
  border-radius: 6px;
  color: #bb9af7;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}

.error-reconnect-btn:hover {
  background: rgba(187, 154, 247, 0.3);
}

.terminal-container {
  flex: 1;
  padding: 8px;
  overflow: hidden;
}

/* Override xterm.js viewport to fill container */
.terminal-container :deep(.xterm) {
  height: 100%;
}

.terminal-container :deep(.xterm-viewport) {
  overflow-y: auto !important;
}
</style>

<style>
/* Unscoped styles for Teleport'd folder picker */
.tcc-folder-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.tcc-folder-picker {
  background: #1a1b26;
  border: 1px solid #292e42;
  border-radius: 10px;
  width: 480px;
  max-height: 500px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.tcc-folder-picker__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #292e42;
}

.tcc-folder-picker__header h4 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #c0caf5;
}

.tcc-folder-picker__close {
  background: none;
  border: none;
  color: #565f89;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.tcc-folder-picker__close:hover {
  color: #c0caf5;
  background: rgba(255, 255, 255, 0.05);
}

.tcc-folder-picker__nav {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #292e42;
  background: #16161e;
}

.tcc-folder-picker__up {
  background: none;
  border: 1px solid #292e42;
  color: #7aa2f7;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.tcc-folder-picker__up:hover:not(:disabled) {
  background: rgba(122, 162, 247, 0.15);
  border-color: rgba(122, 162, 247, 0.3);
}

.tcc-folder-picker__up:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.tcc-folder-picker__path {
  font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace;
  color: #7aa2f7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tcc-folder-picker__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  max-height: 300px;
  min-height: 120px;
}

.tcc-folder-picker__loading,
.tcc-folder-picker__empty {
  text-align: center;
  padding: 24px;
  color: #565f89;
  font-size: 0.75rem;
}

.tcc-folder-picker__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  background: none;
  border: none;
  border-radius: 5px;
  color: #a9b1d6;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.1s;
  text-align: left;
}

.tcc-folder-picker__item:hover {
  background: rgba(122, 162, 247, 0.1);
  color: #c0caf5;
}

.tcc-folder-picker__item svg {
  color: #e0af68;
  flex-shrink: 0;
}

.tcc-folder-picker__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #292e42;
}

.tcc-btn-ghost {
  padding: 6px 14px;
  background: none;
  border: 1px solid #292e42;
  border-radius: 6px;
  color: #565f89;
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.15s;
}

.tcc-btn-ghost:hover {
  color: #c0caf5;
  border-color: #414868;
  background: rgba(255, 255, 255, 0.03);
}

.tcc-btn-accent {
  padding: 6px 14px;
  background: rgba(187, 154, 247, 0.2);
  border: 1px solid rgba(187, 154, 247, 0.4);
  border-radius: 6px;
  color: #bb9af7;
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
}

.tcc-btn-accent:hover {
  background: rgba(187, 154, 247, 0.3);
  border-color: #bb9af7;
}
</style>
