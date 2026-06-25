<template>
  <div class="dcviz">
    <p class="dcviz__hint">서브도메인(도메인 용어)과 책임 · 인접 관계.</p>
    <div class="dcviz__grid">
      <div v-for="(s, i) in subDomains" :key="i" class="dcviz__card">
        <input class="dcviz__name" v-model="s.name" placeholder="서브도메인" />
        <input class="dcviz__resp" v-model="s.responsibility" placeholder="한 줄 책임" />
        <div v-if="s.eventRefs?.length" class="dcviz__refs">{{ s.eventRefs.join(' · ') }}</div>
      </div>
    </div>
    <div v-if="adjacency.length" class="dcviz__adj">
      <h5>인접 관계</h5>
      <span v-for="(a, i) in adjacency" :key="i" class="dcviz__edge">{{ a.from }} → {{ a.to }}</span>
    </div>
    <ul v-if="model.couplingNotes?.length" class="dcviz__notes">
      <li v-for="(n, i) in model.couplingNotes" :key="i">{{ n }}</li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const model = defineModel({ type: Object, required: true })
const subDomains = computed(() => model.value.subDomains || (model.value.subDomains = []))
const adjacency = computed(() => model.value.adjacency || [])
</script>

<style scoped>
.dcviz__hint { font-size: 11px; color: var(--color-text-light); margin: 0 0 8px; }
.dcviz__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.dcviz__card { border: 1px solid var(--color-border); border-radius: 8px; padding: 8px; }
.dcviz__name { width: 100%; font-size: 13px; font-weight: 600; padding: 2px 4px; border: none; border-bottom: 1px solid var(--color-border); background: transparent; color: var(--color-text-bright); box-sizing: border-box; }
.dcviz__resp { width: 100%; font-size: 11px; padding: 4px; margin-top: 4px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); box-sizing: border-box; }
.dcviz__refs { font-size: 10px; color: var(--color-text-light); margin-top: 4px; }
.dcviz__adj { margin-top: 10px; }
.dcviz__adj h5 { margin: 0 0 4px; font-size: 12px; }
.dcviz__edge { display: inline-block; font-size: 11px; background: var(--color-bg-tertiary); border-radius: 10px; padding: 2px 8px; margin: 2px; }
.dcviz__notes { font-size: 11px; color: var(--color-text-light); margin-top: 8px; padding-left: 16px; }
</style>
