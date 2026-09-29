<script setup>
/**
 * 인증 강제 여부를 **아직 모르는 동안** 보여 주는 화면.
 *
 * 왜 이 화면이 필요한가. 전에는 이 순간에 런처나 작업화면이 그려졌다.
 * `provider` 가 null 이면 `enforced` 가 false 로 접혔기 때문이다. 즉
 * **"인증 서버에 못 닿았다" 가 "인증이 꺼져 있다" 로 읽혔다.** 실측으로
 * 창이 뜬 뒤 백엔드가 응답하기까지 44초였고, 첫 설치에서는 2분을 넘을 수
 * 있다(desktop/src/main/backend.ts). 그 사이가 통째로 열려 있었다.
 *
 * 그래서 모르는 동안에는 열지 않고 여기서 기다린다. 기다리는 게 화면이
 * 멈춘 것처럼 보이지 않도록 경과 시간과 무엇을 기다리는지 같이 적는다 —
 * 처음 켜는 사람은 "고장" 과 "원래 오래 걸림" 을 구별할 방법이 없다.
 */
import { computed, onUnmounted, ref } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'

const props = defineProps({
  /** `'checking'` 또는 `'unreachable'`. 스토어의 `gate` 값을 그대로 받는다. */
  state: { type: String, required: true },
})

const auth = useAuthStore()
const elapsed = ref(0)
const timer = setInterval(() => { elapsed.value += 1 }, 1000)
onUnmounted(() => clearInterval(timer))

/** 첫 기동은 원래 오래 걸린다. 그 사실을 15초쯤부터 알려 준다. */
const slow = computed(() => elapsed.value >= 15)
const retrying = ref(false)

async function retry() {
  retrying.value = true
  try {
    await auth.loadProvider({ attempts: 30, delayMs: 1000 })
  } finally {
    retrying.value = false
  }
}
</script>

<template>
  <div class="gate">
    <div class="gate__card">
      <div class="gate__brand">Robo Architect</div>
      <div class="gate__line"></div>

      <template v-if="props.state === 'checking'">
        <div class="gate__spinner" aria-hidden="true"></div>
        <h1 class="gate__title">인증 설정을 확인하는 중입니다</h1>
        <p class="gate__desc">
          누구인지 확인되기 전에는 아무것도 열지 않습니다.
        </p>
        <div class="gate__elapsed">{{ elapsed }}초 경과</div>
        <p v-if="slow" class="gate__note">
          Docker 스택과 백엔드가 함께 뜨는 중입니다.
          <strong>처음 켤 때는 2분을 넘길 수 있습니다.</strong>
        </p>
      </template>

      <template v-else>
        <h1 class="gate__title">인증 서버에 닿지 못했습니다</h1>
        <p class="gate__desc">
          로그인을 강제하는지 확인할 수 없어 <strong>열지 않았습니다.</strong><br />
          확인하지 못한 것을 "인증이 꺼져 있다" 로 읽지 않습니다.
        </p>
        <div class="gate__what">
          <div class="gate__whathead">확인할 것</div>
          <ol>
            <li>Docker Desktop 이 실행 중인지</li>
            <li>트레이 아이콘의 <code>엔진 상태</code> 가 준비됐는지</li>
            <li>그래도 안 되면 앱을 끄고 다시 켜기</li>
          </ol>
        </div>
        <button class="gate__primary" :disabled="retrying" @click="retry">
          {{ retrying ? '다시 확인하는 중…' : '다시 확인' }}
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* 로그인 화면과 같은 토큰을 쓴다 — 두 화면이 이어져 보여야 한다. */
.gate { position:fixed; inset:0; display:flex; align-items:center; justify-content:center;
  background:var(--color-bg); font-family:var(--font-main); z-index:9999; }
.gate__card { width:380px; background:var(--color-bg-secondary);
  border:1px solid var(--color-border); border-radius:var(--radius-md);
  padding:var(--spacing-xl) 36px; text-align:center; }
.gate__brand { font-size:0.7rem; font-weight:700; letter-spacing:3px; text-transform:uppercase;
  color:var(--color-accent); }
.gate__line { width:44px; height:2px; background:var(--color-accent);
  margin:var(--spacing-md) auto var(--spacing-lg); }
.gate__spinner { width:22px; height:22px; margin:0 auto var(--spacing-md);
  border:2px solid var(--color-border); border-top-color:var(--color-accent);
  border-radius:50%; animation:gate-spin 0.9s linear infinite; }
@keyframes gate-spin { to { transform:rotate(360deg); } }
.gate__title { font-size:1.05rem; font-weight:600; color:var(--color-text-bright);
  margin:0 0 var(--spacing-sm); }
.gate__desc { font-size:0.8rem; color:var(--color-text-light); line-height:1.7; margin:0; }
.gate__elapsed { margin-top:var(--spacing-md); font-size:0.72rem; color:var(--color-text-light);
  font-family:var(--font-mono); }
.gate__note { margin:var(--spacing-md) 0 0; font-size:0.74rem; color:var(--color-text-light);
  line-height:1.6; }
.gate__what { margin:var(--spacing-lg) 0 var(--spacing-md); padding-top:var(--spacing-md);
  border-top:1px dashed var(--color-border); text-align:left; }
.gate__whathead { font-size:0.72rem; font-weight:600; color:var(--color-text);
  margin-bottom:var(--spacing-sm); }
.gate__what ol { margin:0; padding-left:18px; font-size:0.76rem; color:var(--color-text-light);
  line-height:1.8; }
.gate__what code { background:var(--color-bg-tertiary); padding:1px 5px;
  border-radius:var(--radius-sm); font-family:var(--font-mono); font-size:0.72rem; }
.gate__primary { width:100%; padding:10px; border:none; border-radius:var(--radius-sm);
  background:var(--color-accent); color:#fff; font-size:0.82rem; font-weight:600;
  font-family:inherit; cursor:pointer; transition:opacity .2s ease; }
.gate__primary:hover:not(:disabled) { opacity:.88; }
.gate__primary:disabled { opacity:.5; cursor:default; }
</style>
