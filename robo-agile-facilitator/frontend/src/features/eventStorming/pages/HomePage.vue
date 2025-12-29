<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../state/session.store'

const router = useRouter()
const sessionStore = useSessionStore()

const title = ref('')
const description = ref('')
const duration = ref(60)
const isCreating = ref(false)

async function createSession() {
  if (!title.value.trim()) return

  isCreating.value = true
  try {
    const session = await sessionStore.createSession(
      title.value,
      description.value || undefined,
      duration.value
    )
    router.push(`/session/${session.id}`)
  } catch (error) {
    console.error('Failed to create session:', error)
    alert('세션 생성에 실패했습니다.')
  } finally {
    isCreating.value = false
  }
}
</script>

<template>
  <div class="home">
    <div class="hero">
      <div class="logo">
        <span class="logo-icon">🎯</span>
        <h1>AESF</h1>
      </div>
      <p class="tagline">AI Event Storming Facilitator</p>
      <p class="description">
        AI 퍼실리테이터와 함께하는 실시간 이벤트 스토밍 워크숍
      </p>
    </div>

    <div class="create-form">
      <h2>새 세션 만들기</h2>

      <div class="form-group">
        <label for="title">세션 제목</label>
        <input
          id="title"
          v-model="title"
          type="text"
          placeholder="예: 주문 도메인 이벤트 스토밍"
          :disabled="isCreating"
        />
      </div>

      <div class="form-group">
        <label for="description">설명 (선택)</label>
        <textarea
          id="description"
          v-model="description"
          placeholder="세션에 대한 간단한 설명..."
          rows="3"
          :disabled="isCreating"
        />
      </div>

      <div class="form-group">
        <label for="duration">진행 시간</label>
        <select id="duration" v-model="duration" :disabled="isCreating">
          <option :value="30">30분</option>
          <option :value="45">45분</option>
          <option :value="60">60분 (권장)</option>
          <option :value="90">90분</option>
          <option :value="120">2시간</option>
        </select>
      </div>

      <button
        class="create-btn"
        :disabled="!title.trim() || isCreating"
        @click="createSession"
      >
        <span v-if="isCreating">생성 중...</span>
        <span v-else>세션 시작하기</span>
      </button>
    </div>

    <div class="features">
      <div class="feature">
        <div class="feature-icon">🗣️</div>
        <h3>실시간 화상회의</h3>
        <p>WebRTC 기반 화상 통화로 팀과 함께 협업</p>
      </div>
      <div class="feature">
        <div class="feature-icon">🤖</div>
        <h3>AI 퍼실리테이터</h3>
        <p>OpenAI가 실시간으로 규칙 검증 및 가이드</p>
      </div>
      <div class="feature">
        <div class="feature-icon">📝</div>
        <h3>실시간 동시 편집</h3>
        <p>여러 명이 동시에 캔버스에서 작업</p>
      </div>
      <div class="feature">
        <div class="feature-icon">📊</div>
        <h3>그래프 기반 저장</h3>
        <p>Neo4j로 관계 중심의 데이터 구조화</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: #fff;
  padding: 2rem;
}

.hero {
  text-align: center;
  padding: 3rem 0;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.logo-icon {
  font-size: 3rem;
}

.logo h1 {
  font-size: 3.5rem;
  font-weight: 800;
  background: linear-gradient(135deg, #e94560 0%, #ff6b6b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
  letter-spacing: 0.1em;
}

.tagline {
  font-size: 1.2rem;
  color: #a0a0a0;
  margin-bottom: 0.5rem;
}

.description {
  font-size: 1.5rem;
  color: #e0e0e0;
  max-width: 600px;
  margin: 0 auto;
}

.create-form {
  max-width: 500px;
  margin: 2rem auto;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 2rem;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.create-form h2 {
  margin: 0 0 1.5rem;
  color: #e94560;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #b0b0b0;
  font-size: 0.9rem;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 0.8rem 1rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 1rem;
  transition: all 0.2s;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: #e94560;
  background: rgba(255, 255, 255, 0.15);
}

.form-group input::placeholder,
.form-group textarea::placeholder {
  color: #707070;
}

.create-btn {
  width: 100%;
  padding: 1rem;
  background: linear-gradient(135deg, #e94560 0%, #ff6b6b 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.create-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(233, 69, 96, 0.4);
}

.create-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem;
  max-width: 1000px;
  margin: 4rem auto;
}

.feature {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.2s;
}

.feature:hover {
  transform: translateY(-4px);
  border-color: #e94560;
}

.feature-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.feature h3 {
  margin: 0 0 0.5rem;
  color: #fff;
}

.feature p {
  margin: 0;
  color: #a0a0a0;
  font-size: 0.9rem;
}
</style>


