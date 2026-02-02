<script setup>
const props = defineProps({
  id: String,
  data: Object
})
</script>

<template>
  <div class="bc-header-node">
    <div class="bc-header__title">{{ data.name }}</div>
    <div class="bc-header__count">
      {{ data.aggregateCount || 0 }} Aggregate{{ data.aggregateCount !== 1 ? 's' : '' }}
    </div>
  </div>
</template>

<style scoped>
.bc-header-node {
  background: linear-gradient(135deg, #373a40 0%, #2c2e33 100%);
  border: 2px solid #495057;
  border-radius: 12px;
  padding: 16px 20px;
  width: 100%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  cursor: default;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.bc-header__title {
  font-size: 1.2rem;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 8px;
  text-align: center;
}

.bc-header__count {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
  font-weight: 500;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
</style>
