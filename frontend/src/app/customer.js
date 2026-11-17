/**
 * 고객 확장이 화면에 주는 값 — **코어가 읽는 유일한 자리**.
 *
 * 빌드가 `VITE_CUSTOMER` 로 `@customer` 를 `extensions/<고객>/frontend/index.js` 에 잇는다
 * (기본은 `extensions/_default`). 코어 코드는 고객 이름으로 분기하지 않고 **이 값만** 본다 —
 * `if (customer === 'posco')` 가 코어에 생기는 순간 고객 차이가 다시 브랜치처럼 퍼진다.
 *
 * 확장은 바꿀 것만 적는다. 안 적은 칸은 아래 기본값(= 지금 main 동작)이다.
 */
import ext from '@customer'

const DEFAULTS = Object.freeze({
  id: 'default',
  shell: {
    // 상단 탭에서 감출 것(예: 사내망에 claude CLI 가 없어 Proposals·Code 를 감춘다).
    hiddenTabs: [],
    // 처음 열 탭. null 이면 셸 기본.
    startTab: null,
  },
  features: {
    // Proposal 생애주기 화면(spec 039~042).
    proposals: true,
    // 헌장(Constitution) 진입점 — Proposals 를 따라간다(헌장을 읽는 것이 Proposal 뿐).
    constitution: null,
  },
  legacy: {
    // 'auto' = 데스크톱이 고른 폴더가 있으면 경로 모드, 없으면 업로드 · 'upload' = 늘 폴더 업로드.
    sourceMode: 'auto',
  },
  projects: {
    // 새 프로젝트에 대상 폴더(Proposals·Code 의 작업 경로)를 받나.
    requireRoot: true,
  },
  deliverables: {
    // 내보내기 형식 허용 목록. null 이면 코어가 아는 형식 전부.
    formats: null,
    // 산출물 파일 이름 틀. null 이면 코어 기본 이름(`{baseName}-YYYY-MM-DD.{ext}`).
    // 칸: {project} {kind} {yyyyMMdd} {HHmmss} — 현지 시각. 확장자는 코어가 붙인다.
    fileNameTemplate: null,
    // 정본화 결과를 사용자에게 말할 때 'ECM 등록' 을 말하나. false 면 일반 문구('정본화').
    ecm: false,
  },
  ai: {
    // AI 게이트웨이를 화면에서 부르는 이름(설정 > AI 호출 경로 · 생성 모델).
    gatewayName: 'AI 게이트웨이',
  },
  templates: {
    // 템플릿 탭이 처음 고를 묶음 이름. null 이면 서버가 주는 첫 묶음.
    defaultSet: null,
    // 템플릿 탭 빈 화면의 설명.
    description: '이벤트 스토밍 요소로 Java 프로젝트를 생성합니다.',
    // 생성 패키지 표시의 앞부분(`<prefix>.<serviceId>.<boundedContext>`).
    packagePrefix: 'com.example',
  },
  // 로고·제품 이름 · 로그인 문구. null 이면 제품 기본.
  brand: null,
})

function merge(base, over) {
  if (!over || typeof over !== 'object' || Array.isArray(over)) return over === undefined ? base : over
  const out = { ...base }
  for (const [k, v] of Object.entries(over)) {
    out[k] = base && typeof base[k] === 'object' && base[k] !== null && !Array.isArray(base[k])
      ? merge(base[k], v)
      : v
  }
  return out
}

const resolved = merge(DEFAULTS, ext || {})
if (resolved.features.constitution === null) {
  resolved.features.constitution = resolved.features.proposals
}

/** 이 빌드의 고객 설정(읽기 전용). */
export const customer = Object.freeze(resolved)

/** 판(edition) — `web` | `desktop`. 진단·로그용. 분기는 `customer` 값으로 한다. */
export const EDITION = typeof __ROBO_EDITION__ === 'string' ? __ROBO_EDITION__ : 'web'

/** 상단 탭 목록에서 이 고객이 감춘 것을 뺀다. */
export function visibleTabs(all) {
  const hidden = new Set(customer.shell.hiddenTabs || [])
  return all.filter((t) => !hidden.has(t))
}
