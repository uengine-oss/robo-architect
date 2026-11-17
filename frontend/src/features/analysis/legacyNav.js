// 레거시 탭의 메뉴 — 앱 레일(SideRail)이 그리고, 끼워 넣은 분석기 화면(AnalysisPanel)이 따른다.
// id 는 분석기 features.config 의 id 다(임베드 노출 4개).
import { ref } from 'vue'

export const LEGACY_FEATURES = [
  { id: 'upload', label: '코드', icon: 'LegacyCode' },
  { id: 'datasources', label: '데이터 소스', icon: 'LegacySources' },
  { id: 'graph', label: '코드 그래프', icon: 'LegacyGraph' },
  { id: 'schema', label: '데이터 스키마', icon: 'LegacySchema' },
]

/** 분석기가 지금 보여 주는 메뉴 */
export const legacyFeature = ref('upload')

let setter = null
/** AnalysisPanel 이 분석기를 띄운 뒤 메뉴 바꾸는 함수를 건다(내리면 null). */
export function bindLegacyNav(fn) { setter = fn }
export function openLegacyFeature(id) {
  legacyFeature.value = id
  setter?.(id)
}
