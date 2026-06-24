<template>
  <div class="dviz">
    <p class="dviz__hint">도메인 이벤트 타임라인. ⭐ Pivotal · 🟪 외부 · 🔥 Hotspot(해결시점 선택).</p>
    <ol class="dviz__timeline">
      <li v-for="(e, i) in events" :key="i" class="dviz__evt">
        <span class="dviz__dot" :class="{ 'is-pivot': isPivot(e.name), 'is-ext': e.external }" />
        <input class="dviz__name" v-model="e.name" />
        <input class="dviz__actor" v-model="e.actor" placeholder="actor" />
        <label class="dviz__tag"><input type="checkbox" :checked="isPivot(e.name)" @change="togglePivot(e.name)" /> ⭐</label>
        <label class="dviz__tag"><input type="checkbox" v-model="e.external" /> 🟪</label>
      </li>
    </ol>

    <div v-if="hotspots.length" class="dviz__hot">
      <h5>🔥 Hotspots</h5>
      <div v-for="(h, i) in hotspots" :key="i" class="dviz__hotrow">
        <input class="dviz__name" v-model="h.text" />
        <label class="dviz__tag"><input type="radio" :name="`h${i}`" value="RESOLVE_NOW" v-model="h.disposition" /> 지금</label>
        <label class="dviz__tag"><input type="radio" :name="`h${i}`" value="DEFER" v-model="h.disposition" /> 보류</label>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const model = defineModel({ type: Object, required: true })
const events = computed(() => model.value.events || (model.value.events = []))
const hotspots = computed(() => model.value.hotspots || (model.value.hotspots = []))
function isPivot(name) { return (model.value.pivotalEvents || []).includes(name) }
function togglePivot(name) {
  if (!model.value.pivotalEvents) model.value.pivotalEvents = []
  const arr = model.value.pivotalEvents
  const i = arr.indexOf(name)
  if (i >= 0) arr.splice(i, 1); else arr.push(name)
}
</script>

<style scoped>
.dviz__hint { font-size: 11px; color: var(--color-text-light); margin: 0 0 8px; }
.dviz__timeline { list-style: none; padding: 0; margin: 0; border-left: 2px solid var(--color-border); }
.dviz__evt { display: flex; align-items: center; gap: 6px; padding: 3px 0 3px 12px; position: relative; }
.dviz__dot { position: absolute; left: -7px; width: 10px; height: 10px; border-radius: 50%; background: var(--color-border); }
.dviz__dot.is-pivot { background: var(--color-accent); }
.dviz__dot.is-ext { background: #a855f7; }
.dviz__name { flex: 1; font-size: 12px; padding: 2px 6px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); }
.dviz__actor { width: 90px; font-size: 11px; padding: 2px 6px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); }
.dviz__tag { font-size: 11px; white-space: nowrap; }
.dviz__hot { margin-top: 10px; }
.dviz__hot h5 { margin: 0 0 4px; font-size: 12px; color: var(--color-danger); }
.dviz__hotrow { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
</style>
