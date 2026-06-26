<script setup>
// US: "상품을 장바구니에 담고 주문한다"
// 장바구니 화면 — 담기 / 삭제 / 주문(Checkout).
import { ref } from 'vue'
import { cartApi } from '../api/shopApi'

const customerId = ref('')
const productId = ref('')
const quantity = ref(1)
const cartId = ref(null)
const items = ref([])
const message = ref('')

async function addItem() {
  const res = await cartApi.addItem(customerId.value, productId.value, Number(quantity.value))
  cartId.value = res.cartId
  items.value.push({ productId: productId.value, quantity: Number(quantity.value) })
  message.value = '장바구니에 담았습니다'
}

async function removeItem(pid) {
  await cartApi.removeItem(cartId.value, pid)
  items.value = items.value.filter((it) => it.productId !== pid)
  message.value = '항목을 삭제했습니다'
}

async function checkout() {
  await cartApi.checkout(cartId.value)
  message.value = '주문이 접수되었습니다(Checkout 완료)'
  items.value = []
}
</script>

<template>
  <section class="cart-view">
    <h1>장바구니</h1>

    <form class="add-form" @submit.prevent="addItem">
      <input v-model="customerId" placeholder="고객 ID" required />
      <input v-model="productId" placeholder="상품 ID" required />
      <input v-model.number="quantity" type="number" min="1" required />
      <button type="submit">담기</button>
    </form>

    <ul class="items">
      <li v-for="it in items" :key="it.productId">
        {{ it.productId }} × {{ it.quantity }}
        <button @click="removeItem(it.productId)">삭제</button>
      </li>
    </ul>

    <button class="checkout" :disabled="!items.length" @click="checkout">
      주문하기 (Checkout)
    </button>

    <p v-if="message" class="message">{{ message }}</p>
  </section>
</template>
