<script setup>
/**
 * 상단의 프로젝트 선택기.
 *
 * 어느 프로젝트를 보고 있는지가 늘 보여야 한다 — 프로젝트마다 설계가 통째로
 * 다르므로, 모르고 남의 프로젝트를 고친 것을 나중에 알면 되돌릴 방법이 없다.
 *
 * 고르면 새로고침한다. 각 스토어를 하나씩 비우는 길을 만들면 빠뜨린 곳이 이전
 * 데이터를 계속 보여 주는데, 그건 오류 없이 틀린 화면이다.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'
import { useProjectsStore } from '../projects.store.js'

const auth = useAuthStore()
const store = useProjectsStore()

const open = ref(false)
const mode = ref('list')      // list | create | share
const newName = ref('')
const inviteUid = ref('')
const inviteLevel = ref('read')
const memberList = ref([])
const busy = ref(false)
const message = ref('')

const LEVEL_LABEL = { read: '읽기', write: '편집', admin: '관리' }

/** 로그인하지 않았으면 고를 것이 없다. 목록이 비었다고 안내하면 오해를 준다. */
const signedIn = computed(() => !!auth.token)

async function refresh() {
  if (!signedIn.value) return
  await store.load()
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    mode.value = 'list'
    message.value = ''
    refresh()
  }
}

async function submitCreate() {
  if (!newName.value.trim()) return
  busy.value = true
  message.value = ''
  try {
    const p = await store.create(newName.value.trim())
    newName.value = ''
    mode.value = 'list'
    store.select(p.graph)
  } catch (e) {
    message.value = e.message
  } finally {
    busy.value = false
  }
}

async function openShare() {
  mode.value = 'share'
  message.value = ''
  try {
    memberList.value = await store.members(auth.projectGraph)
  } catch (e) {
    message.value = e.message
  }
}

async function submitInvite() {
  if (!inviteUid.value.trim()) return
  busy.value = true
  message.value = ''
  try {
    await store.share(auth.projectGraph, inviteUid.value.trim(), inviteLevel.value)
    inviteUid.value = ''
    memberList.value = await store.members(auth.projectGraph)
  } catch (e) {
    message.value = e.message
  } finally {
    busy.value = false
  }
}

async function revoke(uid) {
  message.value = ''
  try {
    await store.unshare(auth.projectGraph, uid)
    memberList.value = await store.members(auth.projectGraph)
  } catch (e) {
    message.value = e.message
  }
}

onMounted(refresh)
// 로그인하면 그때 목록을 읽는다. 부팅 순서상 토큰이 나중에 붙는 경우가 있다.
watch(() => auth.token, (t) => { if (t) refresh() })
</script>

<template>
  <div class="pp" v-if="signedIn">
    <button class="pp__btn" :class="{ 'pp__btn--none': !store.currentName }" @click="toggle">
      <span class="pp__label">프로젝트</span>
      <span class="pp__name">{{ store.currentName || '선택 안 됨' }}</span>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <div v-if="open" class="pp__backdrop" @click="open = false"></div>
    <div v-if="open" class="pp__menu">
      <!-- 목록 -->
      <template v-if="mode === 'list'">
        <div class="pp__head">
          내 프로젝트
          <button class="pp__link" @click="refresh" :disabled="store.loading">새로고침</button>
        </div>
        <p v-if="store.loading" class="pp__note">불러오는 중…</p>
        <p v-else-if="store.error" class="pp__err">{{ store.error }}</p>
        <p v-else-if="!store.projects.length" class="pp__note">
          아직 프로젝트가 없습니다. 아래에서 만들어 주세요.
        </p>
        <ul v-else class="pp__list">
          <li v-for="p in store.projects" :key="p.graph">
            <button class="pp__item" :class="{ 'pp__item--on': p.graph === auth.projectGraph }"
                    @click="store.select(p.graph)">
              <span class="pp__itemname">{{ p.displayName || p.graph }}</span>
              <span class="pp__level">{{ LEVEL_LABEL[p.level] || p.level }}</span>
            </button>
          </li>
        </ul>
        <div class="pp__foot">
          <button class="pp__link" @click="mode = 'create'">＋ 새 프로젝트</button>
          <button v-if="store.canManage" class="pp__link" @click="openShare">공유 관리</button>
        </div>
      </template>

      <!-- 만들기 -->
      <template v-else-if="mode === 'create'">
        <div class="pp__head">새 프로젝트</div>
        <p class="pp__note">
          이름만 정하면 됩니다. 저장 공간과 권한은 함께 만들어집니다.
        </p>
        <form @submit.prevent="submitCreate">
          <input v-model="newName" class="pp__input" placeholder="예: 인사관리 설계" />
          <div class="pp__actions">
            <button type="button" class="pp__link" @click="mode = 'list'">취소</button>
            <button type="submit" class="pp__primary" :disabled="busy || !newName.trim()">만들기</button>
          </div>
        </form>
      </template>

      <!-- 공유 -->
      <template v-else>
        <div class="pp__head">
          공유 — {{ store.currentName }}
          <button class="pp__link" @click="mode = 'list'">뒤로</button>
        </div>
        <ul class="pp__members">
          <li v-for="m in memberList" :key="m.role">
            <span class="pp__m-uid">{{ m.uid || m.role }}</span>
            <span class="pp__m-name">{{ m.displayName || '' }}</span>
            <span class="pp__level">{{ LEVEL_LABEL[m.level] || m.level }}</span>
            <button v-if="m.uid && m.uid !== (store.current || {}).ownerUid"
                    class="pp__revoke" @click="revoke(m.uid)">회수</button>
            <span v-else class="pp__owner">소유자</span>
          </li>
        </ul>
        <form class="pp__invite" @submit.prevent="submitInvite">
          <input v-model="inviteUid" class="pp__input" placeholder="사번" />
          <select v-model="inviteLevel" class="pp__select">
            <option value="read">읽기</option>
            <option value="write">편집</option>
            <option value="admin">관리</option>
          </select>
          <button type="submit" class="pp__primary" :disabled="busy || !inviteUid.trim()">초대</button>
        </form>
      </template>

      <p v-if="message" class="pp__err">{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.pp { position:relative; }
.pp__btn { display:flex; align-items:center; gap:7px; padding:5px 10px; border:1px solid #dee2e6;
  border-radius:6px; background:#fff; cursor:pointer; font-size:12.5px; color:#343a40; }
.pp__btn--none { border-style:dashed; color:#868e96; }
.pp__label { font-size:10.5px; color:#adb5bd; text-transform:uppercase; letter-spacing:.5px; }
.pp__name { font-weight:600; max-width:180px; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.pp__backdrop { position:fixed; inset:0; z-index:900; }
.pp__menu { position:absolute; top:calc(100% + 6px); left:0; z-index:901; width:320px;
  background:#fff; border:1px solid #dee2e6; border-radius:8px; padding:12px;
  box-shadow:0 4px 20px rgba(0,0,0,.10); }
.pp__head { display:flex; align-items:center; justify-content:space-between; font-size:12px;
  font-weight:700; color:#495057; margin-bottom:8px; }
.pp__list, .pp__members { list-style:none; margin:0; padding:0; max-height:240px; overflow-y:auto; }
.pp__item { display:flex; align-items:center; justify-content:space-between; width:100%;
  padding:7px 9px; border:none; border-radius:6px; background:none; cursor:pointer;
  font-size:12.5px; color:#343a40; text-align:left; }
.pp__item:hover { background:#f1f3f5; }
.pp__item--on { background:#e7f5ff; font-weight:600; }
.pp__itemname { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pp__level { font-size:10.5px; color:#868e96; background:#f1f3f5; border-radius:9px;
  padding:1px 7px; margin-left:8px; flex-shrink:0; }
.pp__foot { display:flex; justify-content:space-between; margin-top:10px; padding-top:9px;
  border-top:1px solid #f1f3f5; }
.pp__link { border:none; background:none; color:#228be6; font-size:12px; cursor:pointer; }
.pp__link:disabled { color:#adb5bd; cursor:default; }
.pp__note { font-size:12px; color:#868e96; line-height:1.6; margin:6px 2px 10px; }
.pp__err { font-size:12px; color:#c92a2a; margin:8px 2px 0; }
.pp__input { width:100%; padding:7px 9px; border:1px solid #ced4da; border-radius:6px;
  font-size:12.5px; box-sizing:border-box; }
.pp__select { padding:7px; border:1px solid #ced4da; border-radius:6px; font-size:12.5px; }
.pp__actions { display:flex; justify-content:flex-end; gap:8px; margin-top:10px; }
.pp__primary { padding:6px 12px; border:none; border-radius:6px; background:#228be6; color:#fff;
  font-size:12.5px; cursor:pointer; }
.pp__primary:disabled { opacity:.5; cursor:default; }
.pp__members li { display:flex; align-items:center; gap:8px; padding:6px 2px;
  border-bottom:1px solid #f1f3f5; font-size:12.5px; }
.pp__m-uid { font-weight:600; }
.pp__m-name { color:#868e96; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pp__revoke { border:1px solid #ffc9c9; border-radius:5px; background:#fff; color:#c92a2a;
  font-size:11px; padding:2px 7px; cursor:pointer; }
.pp__owner { font-size:11px; color:#adb5bd; }
.pp__invite { display:flex; gap:6px; margin-top:10px; }
.pp__invite .pp__input { flex:1; }
</style>
