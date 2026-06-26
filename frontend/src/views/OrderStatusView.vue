<script setup>
// US: "주문 상태를 조회한다"
// 주문 상태 조회 화면 — 단일 진실 소스(주문 Aggregate)에서 상태를 읽어온다.
import { ref } from 'vue'
import { orderApi } from '../api/shopApi'

const orderId = ref('')
const status = ref(null)
const error = ref('')

async function fetchStatus() {
  error.value = ''
  status.value = null
  try {
    status.value = await orderApi.getStatus(orderId.value)
  } catch (e) {
    error.value = e.message
  }
}

async function cancel() {
  await orderApi.cancel(orderId.value, '고객 요청')
  await fetchStatus()
}
</script>

<template>
  <section class="order-status-view">
    <h1>주문 상태 조회</h1>

    <form class="lookup" @submit.prevent="fetchStatus">
      <input v-model="orderId" placeholder="주문 ID" required />
      <button type="submit">조회</button>
    </form>

    <div v-if="status" class="status-card">
      <p><strong>주문</strong> {{ status.orderId }}</p>
      <p><strong>상태</strong> {{ status.status }}</p>
      <p><strong>결제 금액</strong> {{ status.totalAmount }}</p>
      <button
        v-if="status.status !== 'Cancelled' && status.status !== 'Confirmed'"
        @click="cancel"
      >
        주문 취소
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>
