<script setup>
const props = defineProps({
  id: String,
  data: Object
})
</script>

<template>
  <div class="aggregate-container-node">
    <!-- BC Name Header -->
    <div class="container-header">
      <div class="bc-name">{{ data.bcName }}</div>
    </div>
    
    <!-- Container content area (children will be positioned here) -->
    <div class="container-content">
      <!-- This area is for child nodes (Aggregate, Enum, VO) -->
    </div>
  </div>
</template>

<style scoped>
.aggregate-container-node {
  width: 100%;
  height: 100%;
  background: rgba(55, 58, 64, 0.25);
  border: 2px solid rgba(73, 80, 87, 0.6);
  border-radius: 12px;
  position: relative;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  overflow: visible;
  display: flex;
  flex-direction: column;
  cursor: move;
  user-select: none;
}

.container-header {
  background: linear-gradient(135deg, #373a40 0%, #2c2e33 100%);
  border-bottom: 2px solid rgba(73, 80, 87, 0.6);
  border-radius: 10px 10px 0 0;
  padding: 10px 16px;
  text-align: center;
  flex-shrink: 0;
  z-index: 1;
  cursor: move;
  user-select: none;
}

.bc-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: #ffffff;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.container-content {
  position: relative;
  flex: 1;
  width: 100%;
  overflow: visible;
}
</style>
