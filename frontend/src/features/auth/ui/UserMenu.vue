<script setup>
/**
 * 지금 누구로 들어와 있는지와 로그아웃.
 *
 * 로그아웃 버튼만 두면 **누구로 들어와 있는지 알 수 없다.** 프로젝트마다 권한이
 * 다르고 개발용 우회 로그인까지 있어, 계정을 착각한 채 작업하는 일이 생긴다.
 * 그래서 사람과 버튼을 같이 둔다.
 *
 * 개발용 우회로 들어왔으면 그 사실을 표시한다 — 사내 배포본에서 이게 보이면
 * 설정이 잘못된 것이다.
 */
import { ref, computed } from 'vue'
import { useAuthStore } from '../auth.store.js'

const auth = useAuthStore()
const open = ref(false)

const user = computed(() => auth.user || {})
const isDev = computed(() => user.value.source === 'dev')
const label = computed(() => user.value.displayName || user.value.uid || '알 수 없음')

/**
 * 로그아웃하고 새로고침한다.
 *
 * 토큰만 지우면 이미 읽어 둔 설계 데이터가 화면에 그대로 남는다. 다음 사람이
 * 앞사람의 프로젝트를 보게 되므로, 프로젝트를 바꿀 때와 같은 이유로 다시 띄운다.
 */
function logout() {
  auth.logout()
  auth.setProject(null)
  window.location.reload()
}
</script>

<template>
  <div class="um" v-if="auth.token && auth.user">
    <button class="um__btn" @click="open = !open" :title="`${label} · 로그아웃`">
      <span class="um__avatar" :class="{ 'um__avatar--dev': isDev }">
        {{ label.slice(0, 1) }}
      </span>
      <span class="um__name">{{ label }}</span>
    </button>

    <div v-if="open" class="um__backdrop" @click="open = false"></div>
    <div v-if="open" class="um__menu">
      <div class="um__who">
        <div class="um__whoname">{{ label }}</div>
        <div class="um__meta">
          <span class="um__uid">{{ user.uid }}</span>
          <span v-if="user.department"> · {{ user.department }}</span>
        </div>
        <div class="um__tags">
          <span v-if="auth.isAdmin" class="um__tag um__tag--admin">관리자</span>
          <span v-if="isDev" class="um__tag um__tag--dev" title="사내 배포본에서는 꺼져 있어야 합니다">
            개발용 로그인
          </span>
        </div>
      </div>
      <button class="um__logout" @click="logout">로그아웃</button>
    </div>
  </div>
</template>

<style scoped>
.um { position:relative; font-family:var(--font-main); }
.um__btn { display:flex; align-items:center; gap:7px; padding:4px 9px 4px 4px;
  border:1px solid var(--color-border); border-radius:16px;
  background:var(--color-bg-tertiary); color:var(--color-text); font-family:inherit;
  font-size:0.72rem; cursor:pointer; transition:all .2s ease; }
.um__btn:hover { border-color:var(--color-accent); color:var(--color-text-bright); }
.um__avatar { display:flex; align-items:center; justify-content:center; width:20px; height:20px;
  border-radius:50%; background:var(--color-accent); color:#fff; font-size:0.66rem;
  font-weight:700; flex-shrink:0; }
.um__avatar--dev { background:var(--color-warning); color:var(--color-bg); }
.um__name { max-width:110px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.um__backdrop { position:fixed; inset:0; z-index:900; }
.um__menu { position:absolute; top:calc(100% + 6px); right:0; z-index:901; width:220px;
  background:var(--color-bg-secondary); border:1px solid var(--color-border);
  border-radius:var(--radius-md); padding:12px; box-shadow:0 6px 24px rgba(0,0,0,.4); }
.um__whoname { font-size:0.82rem; font-weight:600; color:var(--color-text-bright); }
.um__meta { font-size:0.7rem; color:var(--color-text-light); margin-top:3px; }
.um__uid { font-family:var(--font-mono); }
.um__tags { display:flex; gap:5px; margin-top:var(--spacing-sm); flex-wrap:wrap; }
.um__tag { font-size:0.62rem; border-radius:9px; padding:1px 7px; }
.um__tag--admin { background:var(--status-blue-bg); color:var(--status-blue-fg); }
.um__tag--dev { background:var(--status-amber-bg); color:var(--status-amber-fg); }
.um__logout { width:100%; margin-top:12px; padding:7px; border:1px solid var(--color-border);
  border-radius:var(--radius-sm); background:var(--color-bg-tertiary); color:var(--color-text);
  font-family:inherit; font-size:0.74rem; cursor:pointer; transition:all .2s ease; }
.um__logout:hover { border-color:var(--color-danger); color:var(--color-danger); }
</style>
