/**
 * 설정 > AI 호출 경로 — 판에 없는 갈래는 감추고, "어디로" 는 사람이 읽는 말로(2026-11-18).
 */
import { expect, test } from '@playwright/test'

// @ts-expect-error 플레인 JS 모듈
import { visiblePaths, destinationLabel, isShippedPath } from '../../src/features/auth/aiRouting.js'

const STATE = {
  paths: [
    { id: 'architect-backend', label: 'Architect 백엔드', status: 'routed', shipped: true },
    { id: 'embeddings', label: '임베딩', status: 'default', shipped: true },
    { id: 'analyzer-stack', label: '분석기 스택', status: 'config-only', shipped: true },
    { id: 'pdf2bpmn-facade', label: 'pdf2bpmn facade', status: 'routed', shipped: false },
    { id: 'claude-code-pty', label: 'Claude Code PTY', status: 'direct', shipped: null, target: 'anthropic' },
    { id: 'open-pencil-aichat', label: 'open-pencil AIChat', status: 'routed', shipped: true },
  ],
}

test('서버 판(web) — pdf2bpmn·Claude Code 를 감춘다', () => {
  const ids = visiblePaths(STATE, { claudeAvailable: false }).map((p: any) => p.id)
  expect(ids).toEqual(['architect-backend', 'embeddings', 'analyzer-stack', 'open-pencil-aichat'])
})

test('lite(Claude Code 있음) — Claude Code 줄이 보인다', () => {
  const ids = visiblePaths(STATE, { claudeAvailable: true }).map((p: any) => p.id)
  expect(ids).toContain('claude-code-pty')
  expect(ids).not.toContain('pdf2bpmn-facade')
})

test('옛 백엔드의 not-shipped 도 감춘다', () => {
  expect(isShippedPath({ id: 'x', status: 'not-shipped' }, { claudeAvailable: true })).toBe(false)
})

test('어디로 — 게이트웨이 이름 · OpenAI · Anthropic', () => {
  expect(destinationLabel({ status: 'routed' }, 'P-GPT')).toBe('P-GPT')
  expect(destinationLabel({ status: 'default' }, 'P-GPT')).toBe('OpenAI')
  expect(destinationLabel({ status: 'direct', target: 'anthropic' }, 'P-GPT')).toBe('Anthropic')
  expect(destinationLabel({ status: 'config-only' }, 'P-GPT')).toBe('분석기 설정을 따름')
})
