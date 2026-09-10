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

/**
 * 이 프로젝트가 함께 볼 **분석 결과**를 고른다.
 *
 * 처음에는 graph 이름을 타이핑하게 만들었는데, `prj_cf33c40fca_a` 는 내부
 * 식별자다 — 사람에게 시킬 것이 아니다. 오타 하나로 남의 분석을 가리키거나
 * 없는 이름으로 거부당한다. 서버가 고를 수 있는 것만 사람 말로 준다.
 */
const pairFor = ref('')        // 어느 프로젝트를 고치는 중인가
const pairValue = ref('')      // 고른 graph ('' = 쓰지 않음)
const pairOptions = ref([])
const pairLoading = ref(false)

async function openPair(p) {
  pairFor.value = p.graph
  pairValue.value = p.analyzerGraph || ''
  message.value = ''
  pairOptions.value = []
  pairLoading.value = true
  try {
    pairOptions.value = await store.analyzerOptions(p.graph)
  } catch (e) {
    message.value = e.message
  } finally {
    pairLoading.value = false
  }
}

async function submitPair() {
  busy.value = true
  message.value = ''
  try {
    await store.setAnalyzer(pairFor.value, pairValue.value)
    pairFor.value = ''
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
              <span class="pp__itemname">
                {{ p.displayName || p.graph }}
                <!-- 설계는 분석에서 뽑은 룰을 승격시킨 것이라 둘은 한 세트다.
                     짝이 없으면 추적성이 .env 의 분석을 본다 — 보여 줘야 한다. -->
                <span v-if="p.analyzerGraph" class="pp__pair"
                      title="함께 보는 분석 결과. 이 graph 로 분석을 다시 돌리면 지금 결과는 통째로 교체된다.">
                  ⇄ {{ p.analyzerGraph }}
                </span>
                <span v-else class="pp__pair pp__pair--none"
                      title="짝이 없으면 추적성이 .env 의 분석 graph 를 본다 — 다른 프로젝트의 분석일 수 있다">
                  분석 미지정
                </span>
              </span>
              <span class="pp__level">{{ LEVEL_LABEL[p.level] || p.level }}</span>
            </button>
            <button v-if="p.level === 'admin'" class="pp__pairbtn" @click.stop="openPair(p)"
                    title="추적성이 어떤 분석 결과를 근거로 삼을지 고릅니다">
              분석 결과 바꾸기
            </button>
            <form v-if="pairFor === p.graph" class="pp__pairform" @submit.prevent="submitPair">
              <p class="pp__hint">
                이 프로젝트의 <b>추적성</b>이 근거로 삼을 분석 결과입니다.
                레거시 분석을 돌리면 여기 고른 곳에 쌓입니다.
              </p>
              <p v-if="pairLoading" class="pp__note">불러오는 중…</p>
              <select v-else v-model="pairValue" class="pp__input">
                <option value="">쓰지 않음 (추적성이 비어 나옵니다)</option>
                <option v-for="o in pairOptions" :key="o.graph" :value="o.graph">
                  {{ o.label }}{{ o.kind === 'own' ? ' — 권장' : '' }}
                </option>
              </select>
              <p v-if="pairValue && pairValue !== p.graph + '_a'" class="pp__warnline">
                ⚠ 다른 프로젝트와 나눠 쓰는 분석입니다. 여기서 분석을 다시 돌리면
                그쪽 결과도 함께 사라집니다.
              </p>
              <div class="pp__actions">
                <button type="button" class="pp__link" @click="pairFor = ''">취소</button>
                <button type="submit" class="pp__primary" :disabled="busy || pairLoading">저장</button>
              </div>
            </form>
          </li>
        </ul>
        <p class="pp__warn" v-if="store.projects.length">
          ⚠ 레거시 분석은 <b>대상 graph 를 통째로 비우고</b> 다시 씁니다.
          같은 분석 graph 를 쓰는 다른 프로젝트가 있으면 그쪽 결과가 사라집니다.
        </p>
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
/* 상단 막대의 다른 요소와 같은 토큰을 쓴다 — 색을 직접 박으면 테마를 바꿨을 때
   이 조각만 남는다. */
.pp { position:relative; font-family:var(--font-main); }
.pp__btn { display:flex; align-items:center; gap:7px; padding:5px 10px;
  border:1px solid var(--color-border); border-radius:var(--radius-sm);
  background:var(--color-bg-tertiary); color:var(--color-text); font-family:inherit;
  font-size:0.75rem; cursor:pointer; transition:all .2s ease; }
.pp__btn:hover { border-color:var(--color-accent); color:var(--color-text-bright); }
.pp__btn--none { border-style:dashed; color:var(--color-text-light); }
.pp__label { font-size:0.62rem; color:var(--color-text-light); text-transform:uppercase;
  letter-spacing:.5px; }
.pp__name { font-weight:600; max-width:180px; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.pp__backdrop { position:fixed; inset:0; z-index:900; }
.pp__menu { position:absolute; top:calc(100% + 6px); left:0; z-index:901; width:320px;
  background:var(--color-bg-secondary); border:1px solid var(--color-border);
  border-radius:var(--radius-md); padding:12px; box-shadow:0 6px 24px rgba(0,0,0,.4); }
.pp__head { display:flex; align-items:center; justify-content:space-between; font-size:0.72rem;
  font-weight:700; color:var(--color-text); margin-bottom:var(--spacing-sm); }
.pp__list, .pp__members { list-style:none; margin:0; padding:0; max-height:240px;
  overflow-y:auto; }
.pp__item { display:flex; align-items:center; justify-content:space-between; width:100%;
  padding:7px 9px; border:none; border-radius:var(--radius-sm); background:none;
  color:var(--color-text); font-family:inherit; font-size:0.76rem; text-align:left;
  cursor:pointer; transition:background .15s ease; }
.pp__item:hover { background:var(--color-bg-tertiary); }
.pp__item--on { background:var(--status-blue-bg); color:var(--color-text-bright);
  font-weight:600; }
.pp__itemname { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pp__pair { display:block; font-size:0.62rem; font-weight:400; color:var(--color-text-light);
  font-family:var(--font-mono); margin-top:2px; }
.pp__pair--none { color:var(--status-amber-fg); font-family:var(--font-main); }
.pp__level { font-size:0.62rem; color:var(--status-neutral-fg); background:var(--status-neutral-bg);
  border-radius:9px; padding:1px 7px; margin-left:var(--spacing-sm); flex-shrink:0; }
.pp__pairbtn { margin: 2px 0 0 10px; padding: 2px 8px; font-size: 0.68rem;
  font-family: inherit; cursor: pointer; color: var(--color-text-light);
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); }
.pp__pairbtn:hover { color: var(--color-text-bright); border-color: var(--color-accent); }
.pp__pairform { padding: 6px 10px 2px; }
.pp__hint { font-size: 0.7rem; line-height: 1.6; color: var(--color-text-light);
  margin: 0 0 6px; }
.pp__warnline { font-size: 0.68rem; line-height: 1.5; color: var(--status-amber-fg);
  margin: 4px 0 0; }

.pp__warn { font-size:0.68rem; line-height:1.6; color:var(--status-amber-fg);
  background:var(--status-amber-bg); border-radius:var(--radius-sm); padding:6px 9px;
  margin:var(--spacing-sm) 0 0; }
.pp__warn b { font-weight:700; }
.pp__foot { display:flex; justify-content:space-between; margin-top:var(--spacing-sm);
  padding-top:9px; border-top:1px solid var(--color-border); }
.pp__link { border:none; background:none; color:var(--color-accent); font-size:0.72rem;
  font-family:inherit; cursor:pointer; }
.pp__link:disabled { color:var(--color-text-light); cursor:default; }
.pp__note { font-size:0.72rem; color:var(--color-text-light); line-height:1.6;
  margin:6px 2px var(--spacing-sm); }
.pp__err { font-size:0.72rem; color:var(--color-danger); margin:var(--spacing-sm) 2px 0; }
.pp__input { width:100%; padding:7px 9px; border:1px solid var(--color-border);
  border-radius:var(--radius-sm); background:var(--color-bg); color:var(--color-text);
  font-size:0.76rem; font-family:inherit; box-sizing:border-box; }
.pp__input:focus { outline:none; border-color:var(--color-accent); }
.pp__select { padding:7px; border:1px solid var(--color-border); border-radius:var(--radius-sm);
  background:var(--color-bg); color:var(--color-text); font-size:0.76rem; font-family:inherit; }
.pp__actions { display:flex; justify-content:flex-end; gap:var(--spacing-sm);
  margin-top:var(--spacing-sm); }
.pp__primary { padding:6px 12px; border:none; border-radius:var(--radius-sm);
  background:var(--color-accent); color:#fff; font-size:0.76rem; font-family:inherit;
  cursor:pointer; transition:opacity .2s ease; }
.pp__primary:hover:not(:disabled) { opacity:.88; }
.pp__primary:disabled { opacity:.45; cursor:default; }
.pp__members li { display:flex; align-items:center; gap:var(--spacing-sm); padding:6px 2px;
  border-bottom:1px solid var(--color-border); font-size:0.76rem; color:var(--color-text); }
.pp__m-uid { font-weight:600; font-family:var(--font-mono); font-size:0.72rem; }
.pp__m-name { color:var(--color-text-light); flex:1; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.pp__revoke { border:1px solid var(--color-border); border-radius:var(--radius-sm);
  background:var(--status-red-bg); color:var(--status-red-fg); font-size:0.68rem;
  font-family:inherit; padding:2px 7px; cursor:pointer; }
.pp__owner { font-size:0.68rem; color:var(--color-text-light); }
.pp__invite { display:flex; gap:6px; margin-top:var(--spacing-sm); }
.pp__invite .pp__input { flex:1; }
</style>
