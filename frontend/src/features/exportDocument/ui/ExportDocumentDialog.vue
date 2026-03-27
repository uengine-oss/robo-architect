<script setup>
import { ref } from 'vue'
import ExportDocumentTemplate from './ExportDocumentTemplate.vue'

const emit = defineEmits(['close'])

const isOpen = ref(false)
const isExporting = ref(false)
const exportStatus = ref('')
const documentTemplateRef = ref(null)
const showExportMenu = ref(false)

function show() {
  isOpen.value = true
}

function close() {
  if (isExporting.value) return
  isOpen.value = false
  emit('close')
}

// ── Common: extract pages and build page-separated HTML ──
function getScrollArea() {
  return document.querySelector('.export-doc-scroll-area')
}

function buildPagesHtml(scrollArea) {
  const clone = scrollArea.cloneNode(true)
  clone.querySelectorAll('.no-print, .section-selector').forEach(el => el.remove())
  // .page (covers/TOC) → forced page break after each
  clone.querySelectorAll('.page').forEach(el => {
    el.style.pageBreakAfter = 'always'
    el.style.breakAfter = 'page'
  })
  // .block (content) → avoid internal break, natural flow
  clone.querySelectorAll('.block').forEach(el => {
    el.style.pageBreakInside = 'avoid'
    el.style.breakInside = 'avoid'
  })
  // Remove trailing page-break on the very last element (page or block)
  const allEls = clone.querySelectorAll('.page, .block')
  if (allEls.length) {
    const last = allEls[allEls.length - 1]
    last.style.pageBreakAfter = 'auto'
    last.style.breakAfter = 'auto'
  }
  return clone.innerHTML
}

// Common print/export CSS for all formats
const EXPORT_CSS = `
  * { box-sizing: border-box; }
  body { background: #fff; margin: 0; padding: 0; font-family: 'Pretendard', 'Malgun Gothic', -apple-system, sans-serif; color: #1a1a2e; line-height: 1.6; }
  .no-print, .section-selector { display: none !important; }

  /* .page = covers & TOC → each gets its own page */
  .page {
    border: none !important; box-shadow: none !important; border-radius: 0 !important;
    padding: 20px 28px; margin: 0;
    page-break-after: always; break-after: page;
    page-break-inside: avoid; break-inside: avoid;
  }

  /* .block = content → flows naturally, only avoids internal break */
  .block {
    border: none !important; box-shadow: none !important; border-radius: 0 !important;
    padding: 16px 28px; margin: 0;
    page-break-inside: avoid; break-inside: avoid;
  }

  /* Main cover */
  .page--main-cover {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 90vh; text-align: center;
    background: #fff; padding: 80px 40px;
  }
  .main-cover__brand { font-size: 16px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: #228be6; margin-bottom: 16px; }
  .main-cover__line { width: 60px; height: 3px; background: #228be6; margin: 0 auto 40px; }
  .main-cover__title { font-size: 30px; font-weight: 800; color: #1a1a2e; margin: 0 0 12px; }
  .main-cover__sub { font-size: 16px; color: #495057; margin: 0 0 48px; }
  .main-cover__stats { font-size: 13px; color: #868e96; }
  .main-cover__date { font-size: 13px; color: #adb5bd; margin-top: 8px; }

  /* Section cover */
  .page--section-cover {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 60vh; text-align: center;
    background: linear-gradient(135deg, #f8f9fa, #e9ecef);
    padding: 60px 40px;
  }
  .sc__num { font-size: 56px; font-weight: 800; color: #228be6; line-height: 1; margin-bottom: 12px; }
  .sc__title { font-size: 24px; font-weight: 700; color: #1a1a2e; margin-bottom: 10px; }
  .sc__desc { font-size: 14px; color: #6c757d; max-width: 500px; }

  /* TOC */
  .page--toc { padding: 28px 36px; }

  /* Typography */
  h2 { font-size: 18pt; color: #1a1a2e; border-bottom: 2px solid #228be6; padding-bottom: 4px; margin: 0 0 12px; }
  h3 { font-size: 14pt; color: #16213e; margin: 0 0 8px; }
  h4 { font-size: 11pt; color: #495057; margin: 10px 0 4px; }

  /* Tables */
  table { border-collapse: collapse; width: 100%; margin: 6px 0 12px; font-size: 10pt; }
  th { background: #f1f3f5; color: #495057; font-weight: bold; text-align: left; padding: 5px 8px; border: 1px solid #dee2e6; }
  td { padding: 4px 8px; border: 1px solid #dee2e6; vertical-align: top; }

  /* Tags */
  .tag { display: inline-block; font-size: 9pt; padding: 1px 5px; border-radius: 3px; margin: 1px 2px; }
  .tag--event { background: #fff3bf; color: #e67700; }
  .tag--cmd { background: #dbe4ff; color: #364fc7; }
  .tag--rm { background: #d3f9d8; color: #2b8a3e; }
  .dom { display: inline-block; font-size: 9pt; padding: 2px 6px; border-radius: 4px; }
  .dom--CoreDomain { background: #dbe4ff; color: #364fc7; }
  .dom--SupportingDomain { background: #fff3bf; color: #e67700; }
  .dom--GenericDomain { background: #e9ecef; color: #495057; }

  .b { font-weight: 600; }
  .c { text-align: center; }
  .desc { font-size: 10pt; color: #6c757d; margin: 0 0 10px; }
  .desc-cell { font-size: 9pt; color: #6c757d; max-width: 240px; }
  .dim { font-weight: 400; font-size: 9pt; color: #868e96; }
  .meta-line { font-size: 10pt; color: #495057; margin: 4px 0 12px; }
  .empty-note { color: #adb5bd; font-style: italic; }
  .sub { margin-bottom: 14px; }
  .prop-line { line-height: 1.6; }
  .prop-type { color: #868e96; font-size: 9pt; }
  .prop-type::before { content: '('; }
  .prop-type::after { content: ')'; }

  /* Aggregate / Invariants */
  .agg-summary { margin-bottom: 14px; }
  .invariants { margin-top: 6px; font-size: 10pt; }
  .invariants strong { font-size: 10pt; color: #495057; }
  .invariants ul { margin: 4px 0 0; padding-left: 18px; }
  .invariants li { padding: 2px 0; color: #495057; line-height: 1.5; }

  /* BC element list */
  .bc-element-list { margin-top: 12px; }
  .bc-el { font-size: 10pt; padding: 4px 0; }
  .bc-el strong { color: #495057; margin-right: 8px; }

  /* Badges */
  .badge { display: inline-block; font-size: 8pt; padding: 1px 5px; border-radius: 3px; }
  .badge--command { background: #dbe4ff; color: #364fc7; }
  .badge--event { background: #fff3bf; color: #e67700; }
  .badge--policy { background: #fff9db; color: #f08c00; }
  .badge--aggregate { background: #e5dbff; color: #6741d9; }
  .badge--readmodel { background: #d3f9d8; color: #2b8a3e; }

  /* RM card */
  .rm-card { border: 1px solid #e9ecef; border-radius: 6px; padding: 14px 16px; margin-bottom: 12px; }
  .rm-header { margin-bottom: 6px; }

  /* Flow */
  .flow-lane { margin-bottom: 14px; }
  .flow-events { line-height: 2; }
  .flow-chip { font-size: 10pt; color: #343a40; }
  .flow-chip em { font-size: 9pt; color: #868e96; font-style: normal; }
  .flow-arrow { color: #adb5bd; margin: 0 4px; }

  /* Enum/VO */
  .enum-item, .vo-item { font-size: 10pt; padding: 3px 0; }
  .enum-vals { color: #6c757d; margin-left: 6px; }

  /* Mermaid (SVG will be inlined) */
  .ctx-map-wrap { text-align: center; margin: 16px 0; }
  .ctx-map-wrap svg { max-width: 100%; }

  @page { size: A4; margin: 16mm 14mm; }
`

// ── PDF: browser print dialog ──
async function exportToPDF() {
  if (isExporting.value) return
  isExporting.value = true
  exportStatus.value = 'PDF 생성 중...'
  showExportMenu.value = false

  try {
    const scrollArea = getScrollArea()
    if (!scrollArea) throw new Error('내용을 찾을 수 없습니다.')

    const printWindow = window.open('', '_blank')
    if (!printWindow) throw new Error('팝업이 차단되었습니다. 팝업 허용 후 다시 시도하세요.')

    const pagesHtml = buildPagesHtml(scrollArea)

    printWindow.document.write(`<!DOCTYPE html>
<html><head><title>설계 산출물</title><style>${EXPORT_CSS}</style></head>
<body>${pagesHtml}</body></html>`)
    printWindow.document.close()
    printWindow.onload = () => {
      setTimeout(() => { printWindow.print(); printWindow.close() }, 800)
    }
    showSnackbar('인쇄 대화 상자에서 PDF로 저장하세요.', 'success')
  } catch (error) {
    showSnackbar('PDF 생성 실패: ' + (error.message || '알 수 없는 오류'), 'error')
  } finally {
    isExporting.value = false
    exportStatus.value = ''
  }
}

// ── 템플릿 데이터 + 컨테이너 수집 ──
function getExportPayload() {
  const tmpl = documentTemplateRef.value
  if (!tmpl) throw new Error('템플릿 데이터를 찾을 수 없습니다.')
  return {
    data: {
      allContexts: tmpl.allContexts || [],
      fullTrees: tmpl.fullTrees || {},
      sortedContexts: tmpl.sortedContexts || [],
      allUserStories: tmpl.allUserStories || [],
      crossBCPolicies: tmpl.crossBCPolicies || [],
      sectionNumbers: tmpl.sectionNumbers || {},
      selectedSections: tmpl.selectedSections || {},
      helpers: {
        bcName: tmpl.bcName, bcTree: tmpl.bcTree,
        getCommandsFromTree: tmpl.getCommandsFromTree, getReadModelsFromTree: tmpl.getReadModelsFromTree,
        allCmdsForCtx: tmpl.allCmdsForCtx, allEvtsForCtx: tmpl.allEvtsForCtx,
        resolveNodeName: tmpl.resolveNodeName, parseJsonFields: tmpl.parseJsonFields,
      },
    },
    container: document.querySelector('.export-doc-scroll-area'),
  }
}

// ── Word (.docx) — 네이티브 docx (수정 가능) + 다이어그램만 이미지 ──
async function exportToWord() {
  if (isExporting.value) return
  isExporting.value = true
  exportStatus.value = 'Word 문서 생성 중...'
  showExportMenu.value = false

  try {
    const { data, container } = getExportPayload()
    const { exportToWord: doExport } = await import('./exporters/captureExporter')
    await doExport(data, container, (done, total) => {
      exportStatus.value = `Word 생성 중... (${Math.round(done / total * 100)}%)`
    })
    showSnackbar('Word 문서가 생성되었습니다.', 'success')
  } catch (error) {
    console.error('[ExportDoc] Word error:', error)
    showSnackbar('Word 생성 실패: ' + (error.message || '알 수 없는 오류'), 'error')
  } finally {
    isExporting.value = false
    exportStatus.value = ''
  }
}

// ── PowerPoint (.pptx) — 네이티브 pptx (수정 가능) + 다이어그램만 이미지 ──
async function exportToPPT() {
  if (isExporting.value) return
  isExporting.value = true
  exportStatus.value = 'PowerPoint 생성 중...'
  showExportMenu.value = false

  try {
    const { data, container } = getExportPayload()
    const { exportToPPT: doExport } = await import('./exporters/captureExporter')
    await doExport(data, container, (done, total) => {
      exportStatus.value = `PPT 생성 중... (${Math.round(done / total * 100)}%)`
    })
    showSnackbar('PowerPoint가 생성되었습니다.', 'success')
  } catch (error) {
    console.error('[ExportDoc] PPT error:', error)
    showSnackbar('PowerPoint 생성 실패: ' + (error.message || '알 수 없는 오류'), 'error')
  } finally {
    isExporting.value = false
    exportStatus.value = ''
  }
}

// ── Download helper ──
function downloadBlob(blob, ext) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const timestamp = new Date().toISOString().split('T')[0]
  a.download = `설계산출물-${timestamp}.${ext}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })
function showSnackbar(text, color = 'success') {
  snackbar.value = { show: true, text, color }
  setTimeout(() => { snackbar.value.show = false }, 3500)
}

// Close export menu on outside click
function onOverlayClick(e) {
  if (showExportMenu.value) showExportMenu.value = false
}

defineExpose({ show })
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="export-doc-overlay" @click.self="onOverlayClick">
      <div class="export-doc-dialog">
        <!-- Toolbar -->
        <header class="export-doc-toolbar">
          <button class="toolbar-btn toolbar-btn--icon" @click="close" title="닫기">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
          <span class="toolbar-title">설계 산출물 미리보기</span>
          <div class="toolbar-spacer"></div>

          <!-- Export dropdown -->
          <div class="export-dropdown">
            <button
              class="toolbar-btn toolbar-btn--primary"
              :disabled="isExporting"
              @click="showExportMenu = !showExportMenu"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>내보내기</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
            <div v-if="showExportMenu" class="export-dropdown__menu">
              <button class="export-dropdown__item" @click="exportToPDF">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                PDF로 내보내기
              </button>
              <button class="export-dropdown__item" @click="exportToWord">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
                Word (.docx) 로 내보내기
              </button>
              <button class="export-dropdown__item" @click="exportToPPT">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                  <line x1="8" y1="21" x2="16" y2="21"></line>
                  <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
                PowerPoint (.pptx) 로 내보내기
              </button>
            </div>
          </div>
        </header>

        <!-- Scrollable Content -->
        <div class="export-doc-scroll-area">
          <div class="export-doc-content">
            <ExportDocumentTemplate ref="documentTemplateRef" />
          </div>
        </div>

        <!-- Loading overlay -->
        <div v-if="isExporting" class="export-doc-loading">
          <div class="loading-spinner"></div>
          <div class="loading-text">{{ exportStatus }}</div>
        </div>
      </div>

      <!-- Snackbar -->
      <div v-if="snackbar.show" class="export-snackbar" :class="'export-snackbar--' + snackbar.color">
        {{ snackbar.text }}
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.export-doc-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.6);
}

.export-doc-dialog {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #edf0f4;
  overflow: hidden;
  position: relative;
}

/* ── Toolbar ── */
.export-doc-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #1a1a2e;
  color: #fff;
  flex-shrink: 0;
  z-index: 10;
}

.toolbar-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.3px;
}

.toolbar-spacer { flex: 1; }

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  background: transparent;
  color: #fff;
}
.toolbar-btn--icon { padding: 6px; }
.toolbar-btn--icon:hover { background: rgba(255,255,255,0.1); }
.toolbar-btn--primary { background: #228be6; }
.toolbar-btn--primary:hover { background: #1c7ed6; }
.toolbar-btn--primary:disabled { opacity: .5; cursor: not-allowed; }

/* ── Export dropdown ── */
.export-dropdown { position: relative; }

.export-dropdown__menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 220px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.18);
  overflow: hidden;
  z-index: 100;
  animation: menu-in 0.15s ease;
}

@keyframes menu-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.export-dropdown__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #343a40;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.export-dropdown__item:hover { background: #f1f3f5; }
.export-dropdown__item svg { color: #6c757d; flex-shrink: 0; }

/* ── Scroll area ── */
.export-doc-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.export-doc-content {
  max-width: 900px;
  margin: 0 auto;
}

/* ── Loading ── */
.export-doc-loading {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 20;
}

.loading-spinner {
  width: 44px; height: 44px;
  border: 3px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.loading-text { color: #fff; font-size: 14px; font-weight: 500; }

/* ── Snackbar ── */
.export-snackbar {
  position: fixed;
  bottom: 24px; left: 50%; transform: translateX(-50%);
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 13px; font-weight: 500; color: #fff;
  z-index: 10000;
  animation: snackbar-in 0.3s ease;
}
.export-snackbar--success { background: #2b8a3e; }
.export-snackbar--error { background: #c92a2a; }

@keyframes snackbar-in {
  from { opacity: 0; transform: translateX(-50%) translateY(10px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>
