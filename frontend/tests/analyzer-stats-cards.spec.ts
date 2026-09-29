import { test, expect } from '@playwright/test'

/**
 * 분석 결과 요약이 **분석기가 낸 것을 버리지 않는가**.
 *
 * ## 2026-09-29 실측
 *
 * 자동납부0929(hr-sample, Java)에서 `/api/ingest/stats` 는 **20종 1306개**를
 * 돌려주는데 화면은 두 칸만 보여줬다 —
 *
 *     RULE 75 · 테이블 15
 *
 * CLASS 30 · METHOD 171 · COLUMN 101 · PACKAGE 7 이 전부 화면 밖이었다.
 * "분석이 덜 됐나" 로 읽히는 것이 당연하다.
 *
 * 원인은 카드 목록이 `FUNCTION · RULE · EXAMPLE · QUESTION · TABLE` 다섯으로
 * 하드코딩돼 있었고 그 목록이 **C/DBMS 분석의 모양**이었다는 것이다. Java 는
 * 함수가 `METHOD` 라 `FUNCTION` 이 0이고, `EXAMPLE`·`QUESTION` 도 안 나온다.
 *
 * ## 그래서 무엇을 재는가
 *
 * 화면 코드를 직접 켜지 않고, **같은 규칙을 이 파일에 옮겨 적어** 두 언어의
 * 실제 응답으로 확인한다. 화면이 규칙을 바꾸면 이 검사도 같이 고쳐야 하는데,
 * 그 순간이 바로 "이번에도 무엇을 떨어뜨리는가" 를 다시 보게 되는 자리다.
 */

// --- 화면과 같은 규칙 (RequirementsIngestionModal.vue 의 analyzerCards) ---
const ORDER: [string, string][] = [
  ['PACKAGE', '패키지'], ['FILE', '파일'], ['CLASS', '클래스'],
  ['FUNCTION', '함수'], ['METHOD', '메서드'], ['FIELD', '필드'],
  ['CONSTANT_FIELD', '상수'], ['TABLE', '테이블'], ['COLUMN', '컬럼'],
  ['EXAMPLE', 'Example'], ['QUESTION', 'Question'],
]

function cards(counts: Record<string, number>) {
  const out: { key: string; label: string; value: number; accent?: boolean; hint?: string }[] = []
  if (counts.RULE) out.push({ key: 'RULE', label: 'Rule', value: counts.RULE, accent: true })
  for (const [key, label] of ORDER) if (counts[key]) out.push({ key, label, value: counts[key] })
  const named = new Set(['RULE', ...ORDER.map(([k]) => k)])
  const rest = Object.entries(counts).filter(([k, v]) => !named.has(k) && v)
  if (rest.length > 0) {
    out.push({
      key: '__rest',
      label: `구문 ${rest.length}종`,
      value: rest.reduce((s, [, v]) => s + v, 0),
      hint: rest.sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(' · '),
    })
  }
  return out
}

/** hr-sample(Java) — 2026-09-29 `/api/ingest/stats` 실제 응답. */
const JAVA: Record<string, number> = {
  TRY: 58, PACKAGE: 7, CONTINUE: 2, CLASS: 30, TABLE: 15, FILE: 1, FIELD: 45,
  IF: 89, METHOD: 171, CATCH: 62, VARIABLE: 5, LOOP: 14, RETURN: 122, THROW: 99,
  CONSTANT_FIELD: 43, FINALLY: 50, ASSIGNMENT: 314, RULE: 75, COLUMN: 101, ELSE: 3,
}

/** 자동납부(C) — 같은 날 분석 그래프 실측. */
const C_CODE: Record<string, number> = {
  ASSIGNMENT: 192, BREAK: 4, CASE: 9, DEFINE: 12, ELSE: 87, FILE: 2, FUNCTION: 38,
  GLOBAL_VARIABLE: 10, IF: 212, LABEL: 10, LOOP: 4, PACKAGE: 1, RETURN: 132,
  RULE: 156, SWITCH: 3,
}

const sum = (c: Record<string, number>) => Object.values(c).reduce((a, b) => a + b, 0)
const shown = (cs: ReturnType<typeof cards>) => cs.reduce((a, c) => a + c.value, 0)

test.describe('아무것도 떨어뜨리지 않는다', () => {
  for (const [name, counts] of [['Java(hr-sample)', JAVA], ['C(자동납부)', C_CODE]] as const) {
    test(`${name} — 카드 값의 합이 전체와 같다`, () => {
      expect(shown(cards(counts)), '합치는 건 되지만 버리는 건 안 된다').toBe(sum(counts))
    })

    test(`${name} — 모든 라벨이 카드나 툴팁 중 한 곳에는 나온다`, () => {
      const cs = cards(counts)
      const inCards = new Set(cs.map((c) => c.key))
      const hint = cs.find((c) => c.key === '__rest')?.hint || ''
      for (const key of Object.keys(counts)) {
        expect(inCards.has(key) || hint.includes(key), `${key} 가 어디에도 없다`).toBe(true)
      }
    })
  }
})

test.describe('언어가 달라도 빈 화면이 되지 않는다', () => {
  test('Java 에서 클래스·메서드가 보인다 — 예전에는 둘 다 화면 밖이었다', () => {
    const labels = cards(JAVA).map((c) => c.label)
    expect(labels).toContain('클래스')
    expect(labels).toContain('메서드')
    expect(labels).toContain('컬럼')
    expect(labels).toContain('패키지')
  })

  test('C 에서는 함수가 보이고 메서드 칸은 없다', () => {
    const labels = cards(C_CODE).map((c) => c.label)
    expect(labels).toContain('함수')
    expect(labels).not.toContain('메서드')
  })

  test('Rule 은 맨 앞이고 강조된다 — 이 화면의 핵심이다', () => {
    for (const counts of [JAVA, C_CODE]) {
      const first = cards(counts)[0]!
      expect(first.key).toBe('RULE')
      expect(first.accent).toBe(true)
    }
  })

  test('옛 고정 목록이었다면 Java 는 두 칸뿐이다 — 회귀 근거', () => {
    // 이 줄이 예전 동작이다. 되돌아가면 위 검사들이 깨진다.
    const oldFixed = ['FUNCTION', 'RULE', 'EXAMPLE', 'QUESTION', 'TABLE']
      .filter((k) => JAVA[k])
    expect(oldFixed).toEqual(['RULE', 'TABLE'])
  })
})

test.describe('빈 입력에서 터지지 않는다', () => {
  test('분석 전이면 카드가 없다', () => {
    expect(cards({})).toEqual([])
  })

  test('0 인 라벨은 칸을 만들지 않는다', () => {
    expect(cards({ RULE: 0, CLASS: 0, IF: 0 })).toEqual([])
  })
})
