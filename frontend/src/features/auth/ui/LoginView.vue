<script setup>
/**
 * 로그인 화면.
 *
 * 세 가지를 한 화면에서 다룬다 — 로그인, 승인 대기 안내, 거절 안내. 상태마다
 * 화면을 따로 두면 "왜 못 들어가는지"를 사용자가 스스로 알아내야 한다.
 *
 * 개발용 로그인 칸은 **서버가 켜져 있다고 답할 때만** 뜬다. 화면에 숨겨 두고
 * 서버에서 막는 방식이 아니라, 서버의 대답을 그대로 보여 준다.
 */
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../auth.store.js'

const auth = useAuthStore()
const loginId = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

const devLogin = computed(() => (auth.provider || {}).devLogin || {})
const ssoAvailable = computed(() => (auth.provider || {}).provider === 'swp')

onMounted(async () => {
  await auth.loadProvider()
  if (devLogin.value.loginId) loginId.value = devLogin.value.loginId
})

async function submitDev() {
  error.value = ''
  busy.value = true
  try {
    const body = await auth.devLogin(loginId.value, password.value)
    if (!body.accessToken) error.value = ''   // 상태 안내로 넘어간다
  } catch (e) {
    error.value = e.message || '로그인하지 못했습니다.'
  } finally {
    busy.value = false
  }
}

async function submitSso() {
  error.value = ''
  busy.value = true
  try {
    await auth.ssoLogin()
  } catch (e) {
    error.value = e.message || 'SSO 를 시작하지 못했습니다.'
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card">
      <div class="login__brand">Robo Architect</div>
      <div class="login__line"></div>

      <!-- 승인 대기 -->
      <template v-if="auth.pending">
        <h1 class="login__title">승인을 기다리는 중입니다</h1>
        <p class="login__desc">
          계정은 만들어졌습니다. 관리자가 승인하면 바로 사용할 수 있습니다.<br />
          승인 뒤 다시 로그인해 주세요.
        </p>
        <div class="login__who" v-if="auth.user">
          {{ auth.user.displayName || auth.user.uid }}
          <span v-if="auth.user.department"> · {{ auth.user.department }}</span>
        </div>
        <button class="login__ghost" @click="auth.logout()">다른 계정으로</button>
      </template>

      <!-- 거절 -->
      <template v-else-if="auth.rejected">
        <h1 class="login__title">접근이 거절된 계정입니다</h1>
        <p class="login__desc">관리자에게 문의해 주세요.</p>
        <button class="login__ghost" @click="auth.logout()">다른 계정으로</button>
      </template>

      <!-- 로그인 -->
      <template v-else>
        <h1 class="login__title">로그인이 필요합니다</h1>
        <p class="login__desc">사내 인증으로 들어갑니다.</p>

        <button v-if="ssoAvailable" class="login__primary" :disabled="busy" @click="submitSso">
          SWP 로 로그인
        </button>
        <p v-else class="login__note">
          SSO 가 설정돼 있지 않습니다 (<code>AUTH_PROVIDER</code>).
        </p>

        <!-- 개발용 우회. 서버가 켜져 있다고 답할 때만 보인다. -->
        <form v-if="devLogin.enabled" class="login__dev" @submit.prevent="submitDev">
          <div class="login__devhead">
            개발용 로그인
            <span class="login__devwarn">사내 배포본에서는 꺼져 있어야 합니다</span>
          </div>
          <input v-model="loginId" class="login__input" placeholder="아이디" autocomplete="username" />
          <input v-model="password" type="password" class="login__input" placeholder="비밀번호"
                 autocomplete="current-password" />
          <button class="login__secondary" type="submit" :disabled="busy">들어가기</button>
        </form>

        <p v-if="error" class="login__error">{{ error }}</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* 앱의 디자인 토큰을 쓴다 — 색을 직접 박으면 테마를 바꿨을 때 이 화면만 남는다. */
.login { position:fixed; inset:0; display:flex; align-items:center; justify-content:center;
  background:var(--color-bg); font-family:var(--font-main); z-index:9999; }
.login__card { width:380px; background:var(--color-bg-secondary);
  border:1px solid var(--color-border); border-radius:var(--radius-md);
  padding:var(--spacing-xl) 36px; text-align:center; }
.login__brand { font-size:0.7rem; font-weight:700; letter-spacing:3px; text-transform:uppercase;
  color:var(--color-accent); }
.login__line { width:44px; height:2px; background:var(--color-accent);
  margin:var(--spacing-md) auto var(--spacing-lg); }
.login__title { font-size:1.15rem; font-weight:600; color:var(--color-text-bright);
  margin:0 0 var(--spacing-sm); }
.login__desc { font-size:0.8rem; color:var(--color-text-light); line-height:1.7;
  margin:0 0 var(--spacing-lg); }
.login__who { font-size:0.78rem; color:var(--color-text); background:var(--color-bg-tertiary);
  border-radius:var(--radius-sm); padding:var(--spacing-sm) 12px; margin-bottom:var(--spacing-md); }
.login__primary { width:100%; padding:10px; border:none; border-radius:var(--radius-sm);
  background:var(--color-accent); color:#fff; font-size:0.82rem; font-weight:600;
  font-family:inherit; cursor:pointer; transition:opacity .2s ease; }
.login__primary:hover:not(:disabled) { opacity:.88; }
.login__primary:disabled { opacity:.5; cursor:default; }
.login__secondary { width:100%; padding:8px; border:1px solid var(--color-border);
  border-radius:var(--radius-sm); background:var(--color-bg-tertiary); color:var(--color-text);
  font-size:0.8rem; font-family:inherit; cursor:pointer; transition:all .2s ease; }
.login__secondary:hover:not(:disabled) { border-color:var(--color-accent);
  color:var(--color-text-bright); }
.login__ghost { border:none; background:none; color:var(--color-text-light); font-size:0.74rem;
  font-family:inherit; cursor:pointer; text-decoration:underline; }
.login__ghost:hover { color:var(--color-text); }
.login__note { font-size:0.74rem; color:var(--color-text-light); }
.login__note code { background:var(--color-bg-tertiary); padding:1px 5px;
  border-radius:var(--radius-sm); font-family:var(--font-mono); }
.login__dev { margin-top:var(--spacing-lg); padding-top:var(--spacing-md);
  border-top:1px dashed var(--color-border); text-align:left; }
.login__devhead { font-size:0.72rem; font-weight:600; color:var(--color-text);
  margin-bottom:var(--spacing-sm); }
.login__devwarn { display:block; font-weight:400; color:var(--color-warning); margin-top:3px; }
.login__input { width:100%; padding:8px 10px; margin-bottom:var(--spacing-sm);
  border:1px solid var(--color-border); border-radius:var(--radius-sm);
  background:var(--color-bg); color:var(--color-text); font-size:0.8rem;
  font-family:inherit; box-sizing:border-box; }
.login__input:focus { outline:none; border-color:var(--color-accent); }
.login__error { margin-top:var(--spacing-md); font-size:0.74rem; color:var(--color-danger); }
</style>
