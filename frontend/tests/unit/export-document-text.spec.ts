/**
 * 산출물 문서의 **글자 적기** — 자르기와 참/거짓 (2026-10-08).
 *
 * `tests/unit/` 에 둔다 — 그 폴더는 `playwright.unit.config.ts` 가 glob 으로 집으므로
 * **이름을 따로 등록하지 않아도 돈다**(등록을 잊으면 검사가 조용히 사라진다).
 *
 * ## 왜 이 검사가 있나
 *
 * 내보낸 Word 문서를 msa-ez 기준 산출물과 견주다가, 우리 쪽에 **의미가 없어지는 자리**
 * 둘이 있었다. 둘 다 검사가 없었고, **화면 미리보기로는 보이지 않았다** — 화면은
 * 자르지 않기 때문이다.
 *
 * ```
 * ① 설명이 낱말 중간에서 끊겼다   .slice(0, 80) · 말줄임 없음
 * ② false 를 '-'(모른다)로 적었다  isMultipleResult || '-'
 * ```
 *
 * 아래 문자열은 꾸민 것이 아니라 **기준 프로젝트(`prj_16972790c0`) 의 실제 값**이다.
 * 어제 배운 것이 그것이었다 — 상상한 값으로 재면 결함을 재현하지 못한다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { clip, resultKind } from '../../src/features/exportDocument/text.js'
// @ts-expect-error 플레인 JS 모듈
import { SECTION_ORDER, sectionShown, sectionNumbers } from '../../src/features/exportDocument/sections.js'

/** 실제 BC 설명 — 178자. 80자에서 자르면 `approval lin` 으로 끊긴다. */
const REAL_BC_DESC =
  'Manages the approval workflow for leave requests, including dynamic approval line generation, ' +
  'approval/rejection actions, and maintaining approval history and status transitions.'

/** 실제 Read Model 설명 — 167자. */
const REAL_RM_DESC =
  'Detailed information about the dynamically generated approval line for a specific leave request, ' +
  'including each step, approver, and the current state of that step.'

test('낱말 중간에서 끊지 않는다 — 실제 BC 설명 178자', () => {
  expect(REAL_BC_DESC.length).toBe(178)
  // 고치기 전에 문서에 들어갔던 모습 — 이것이 결함이다.
  expect(REAL_BC_DESC.slice(0, 80)).toBe(
    'Manages the approval workflow for leave requests, including dynamic approval lin',
  )

  const out = clip(REAL_BC_DESC, 120)
  expect(out.endsWith('…')).toBe(true)
  // 말줄임을 뗀 몸통이 **공백에서 끝난 자리**여야 한다 = 낱말이 안 쪼개졌다.
  const body = out.slice(0, -1)
  expect(REAL_BC_DESC.startsWith(body)).toBe(true)
  expect(REAL_BC_DESC[body.length]).toBe(' ')
  expect(body.length).toBeLessThanOrEqual(120)
})

test('짧은 것은 **건드리지 않는다** — 말줄임도 안 붙인다', () => {
  expect(clip('짧다', 120)).toBe('짧다')
  expect(clip(REAL_RM_DESC, 300)).toBe(REAL_RM_DESC)
})

test('빈 값은 `-` 다 — 빈 칸은 "자리가 없는 것" 과 구별되지 않는다', () => {
  expect(clip(undefined, 80)).toBe('-')
  expect(clip(null, 80)).toBe('-')
  expect(clip('   ', 80)).toBe('-')
})

/** 폭을 센다 — 한글·한자는 2, 나머지는 1 (문서의 글꼴이 그렇게 앉는다). */
function widthOf(s: string): number {
  return [...s].reduce((w, c) => w + (/[ᄀ-ᅟ가-힣⺀-꓏]/.test(c) ? 2 : 1), 0)
}

test('공백이 없는 한 덩이도 **자르고 말줄임을 붙인다** — 띄어쓰기 없는 한글이 그렇다', () => {
  const korean = '휴가신청의생성검증취소를포함한전체생애주기를관리한다'.repeat(6)
  const out = clip(korean, 30)
  expect(out.endsWith('…')).toBe(true)
  // 폭이 한도 안이다. 글자 수로는 15자뿐 — 한글 한 글자가 두 칸을 먹는다.
  expect(widthOf(out.slice(0, -1))).toBeLessThanOrEqual(30)
})

test('`false` 는 **단건이라는 사실**이다 — `-`(모른다)로 적지 않는다', () => {
  expect(resultKind(false)).toBe('단건')
  expect(resultKind(true)).toBe('다건')
  // 고치기 전 코드가 하던 것 — 둘이 같아져 **사실이 사라졌다**.
  expect(false || '-').toBe('-')
  expect(resultKind(false)).not.toBe(resultKind(null))
})

test('모르는 것은 `-` 로 남긴다 — 모르는 것을 아는 척하지 않는다', () => {
  expect(resultKind(null)).toBe('-')
  expect(resultKind(undefined)).toBe('-')
  expect(resultKind('')).toBe('-')
})

test('이미 사람 말로 적힌 값은 그대로 둔다 — 두 번 바꾸지 않는다', () => {
  // 화면 쪽은 `getReadModelsFromTree` 에서 한 번 바꿔 문자열로 들고 있다.
  expect(resultKind('단건')).toBe('단건')
  expect(resultKind('다건')).toBe('다건')
})

test('한도는 **글자 수가 아니라 폭**이다 — 한국어 설명이 칸 높이를 두 배로 만들지 않는다', () => {
  // 실측(10pt · 폭 2800 twips 열) — 한 줄에 라틴 **26자** · 한글 **13자** 가 앉는다.
  // 글자 수로 재면 같은 한도 120 이 영어 **5줄** · 한국어 **10줄** 이 되어
  // **쪽 넘김이 언어에 따라 달라진다.**
  const korean =
    '휴가 신청의 생성과 검증, 취소를 포함한 전체 생애 주기를 관리하며 결재선 생성과 상태 전이, ' +
    '그리고 잔액 차감까지 한 덩이로 다룬다. 승인 이력은 단계마다 남는다.'
  const out = clip(korean, 120)
  expect(out.endsWith('…')).toBe(true)
  expect(widthOf(out.slice(0, -1))).toBeLessThanOrEqual(120)
  // 글자 수로 재던 때라면 120자가 남았을 것이다 — 폭으로 재니 **그 절반쯤**이다.
  expect(out.length).toBeLessThan(80)
})

test('라틴만 있으면 **글자 수와 똑같이** 동작한다 — 지금 문서 출력은 바뀌지 않는다', () => {
  const body = clip(REAL_BC_DESC, 120).slice(0, -1)
  expect(body.length).toBeLessThanOrEqual(120)
  expect(widthOf(body)).toBe(body.length)
  // 자른 자리가 **낱말 경계**다.
  expect(REAL_BC_DESC.startsWith(body)).toBe(true)
  expect(REAL_BC_DESC[body.length]).toBe(' ')
})

// ---------------------------------------------------------------------------
// 2026-10-08 — **내보낸 문서를 열어 보고** 나온 둘
//
// 넷을 고친 뒤 실제 .docx 를 풀어 세었더니 두 가지가 더 있었다. 둘 다 "비어 있다" 와
// "없다" 를 같게 적던 것이다.
// ---------------------------------------------------------------------------

/** 내보내기의 `txt()` 가 하던 것 — 빈 문자열을 `-` 로 바꿨다. */
const oldTxt = (s: unknown) => String(s || '-')
/** 고친 것 — 값이 없으면 `-` 는 **부르는 쪽이** 정한다. */
const newTxt = (s: unknown) => String(s ?? '')

test('**일부러 비운 칸**은 비워 둔다 — `-` 는 "값이 없다" 는 뜻이다', () => {
  // 실측(설계산출물-2026-10-08.docx) — 표 밖에 홀로 `-` 인 문단 **70개**.
  // 표지 11 · 섹션 표지마다 6 · Aggregate 모델 쪽마다 1. 전부 `empty()`(=`para('')`)였다.
  expect(oldTxt('')).toBe('-')
  expect(newTxt('')).toBe('')
  // 원문 근거 표에서 같은 US 의 둘째 줄은 ID·Task 를 비워 "위와 같다" 로 읽히게 둔다.
  // `-` 가 찍히면 **"업무 Task 가 없다"** 로 보인다(실제로는 33개 US 전부 있었다).
  expect(newTxt('')).not.toBe('-')
  // 값이 **진짜 없을** 때는 여전히 `-` 다 — 표가 `String(c ?? '-')` 로 가른다.
  expect(String(null ?? '-')).toBe('-')
  expect(String(undefined ?? '-')).toBe('-')
})

test('숫자 0 을 `-` 로 바꾸지 않는다 — 0 은 값이다', () => {
  expect(oldTxt(0)).toBe('-')
  expect(newTxt(0)).toBe('0')
})

test('**안 실린 섹션이 번호를 먹지 않는다** — 문서 업로드 없이 생성한 경우', () => {
  const allOn = Object.fromEntries(SECTION_ORDER.map((k: string) => [k, true]))
  // 코드 분석 문서를 올리지 않으면 밸류 스트림·추적성이 비고, Aggregate 는 있다.
  const shown = sectionShown(allOn, { valueStreamCount: 0, aggregateDesignCount: 5, hasTraceSummary: false })
  expect(shown.valueStream).toBe(false)
  expect(shown.traceabilityMatrix).toBe(false)
  // 비어도 "없습니다" 를 적는 섹션은 **실린다** — 빈 것과 안 실리는 것은 다르다.
  expect(shown.userStories).toBe(true)

  const nums = sectionNumbers(shown)
  expect(nums.valueStream).toBeUndefined()
  expect(nums.traceabilityMatrix).toBeUndefined()
  // 번호가 **1부터 빈틈없이** 이어진다 — `1 → 3` 으로 뛰면 섹션이 빠진 문서로 보인다.
  expect(SECTION_ORDER.filter((k: string) => nums[k]).map((k: string) => nums[k])).toEqual([1, 2, 3, 4, 5, 6])
})

test('데이터가 다 있으면 여덟 개가 **1~8** 로 간다', () => {
  const allOn = Object.fromEntries(SECTION_ORDER.map((k: string) => [k, true]))
  const nums = sectionNumbers(sectionShown(allOn, { valueStreamCount: 3, aggregateDesignCount: 5, hasTraceSummary: true }))
  expect(SECTION_ORDER.map((k: string) => nums[k])).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
})

test('섹션을 **끄면** 그 번호도 사라지고 나머지가 당겨진다', () => {
  const shown = sectionShown(
    { userStories: true, boundedContext: true, modelOverview: true, aggregateDetail: true },
    { valueStreamCount: 3, aggregateDesignCount: 5, hasTraceSummary: true },
  )
  const nums = sectionNumbers(shown)
  expect(nums).toEqual({ userStories: 1, boundedContext: 2, modelOverview: 3, aggregateDetail: 4 })
})
