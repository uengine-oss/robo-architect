/**
 * 프로젝트 목록과 선택.
 *
 * 프로젝트는 graph 하나다. 고른 값은 `auth.projectGraph` 에 두고, `fetch`
 * 인터셉터가 그것을 `X-Project-Graph` 로 실어 보낸다 — 화면마다 챙기지 않는다.
 *
 * **바꾸면 새로고침한다.** 설계·캔버스·네비게이터 스토어가 각자 데이터를 들고
 * 있어, 하나씩 비우는 길을 만들면 빠뜨린 곳이 이전 프로젝트 데이터를 계속 보여
 * 준다. 그건 오류 없이 틀린 화면이라 가장 나쁜 실패다.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'

export const useProjectsStore = defineStore('projects', () => {
  const auth = useAuthStore()
  const projects = ref([])
  const loading = ref(false)
  /** null = 아직 안 불러옴, '' = 불러왔고 오류 없음 */
  const error = ref(null)

  const current = computed(
    () => projects.value.find(p => p.graph === auth.projectGraph) || null,
  )
  const currentName = computed(
    () => (current.value && current.value.displayName) || auth.projectGraph || null,
  )
  const canManage = computed(() => (current.value || {}).level === 'admin')

  async function load() {
    loading.value = true
    try {
      const r = await fetch('/api/projects')
      if (r.status === 401) {
        // 로그인하지 않은 상태. 오류가 아니라 아직 고를 수 없는 상태다.
        projects.value = []
        error.value = ''
        return
      }
      if (!r.ok) throw new Error(`목록을 불러오지 못했습니다 (${r.status})`)
      projects.value = (await r.json()).projects || []
      error.value = ''
      // 고른 프로젝트가 목록에 없으면(권한이 회수됐거나 지워졌다) 선택을 비운다.
      if (auth.projectGraph && !projects.value.some(p => p.graph === auth.projectGraph)) {
        auth.setProject(null)
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function create(name) {
    const r = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(body.detail || `만들지 못했습니다 (${r.status})`)
    await load()
    return body
  }

  async function adopt(graph, name) {
    const r = await fetch('/api/projects/adopt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ graph, name }),
    })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(body.detail || `등록하지 못했습니다 (${r.status})`)
    await load()
    return body
  }

  async function members(graph) {
    const r = await fetch(`/api/projects/${encodeURIComponent(graph)}/members`)
    if (!r.ok) throw new Error(`참여자를 불러오지 못했습니다 (${r.status})`)
    return (await r.json()).members || []
  }

  async function share(graph, uid, level) {
    const r = await fetch(`/api/projects/${encodeURIComponent(graph)}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, level }),
    })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(body.detail || `초대하지 못했습니다 (${r.status})`)
    return body
  }

  async function unshare(graph, uid) {
    const r = await fetch(
      `/api/projects/${encodeURIComponent(graph)}/members/${encodeURIComponent(uid)}`,
      { method: 'DELETE' },
    )
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(body.detail || `회수하지 못했습니다 (${r.status})`)
    return body
  }

  /**
   * 프로젝트를 바꾼다.
   *
   * 같은 프로젝트를 다시 고르면 아무 일도 하지 않는다 — 새로고침이 따라오므로
   * 잘못 눌렀을 때 작업이 날아가면 안 된다.
   */
  function select(graph, { reload = true } = {}) {
    if (!graph || graph === auth.projectGraph) return false
    auth.setProject(graph)
    if (reload) window.location.reload()
    return true
  }

  return {
    projects, loading, error, current, currentName, canManage,
    load, create, adopt, members, share, unshare, select,
  }
})
