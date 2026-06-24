<template>
  <div class="tviz">
    <p class="tviz__hint">Aggregate Design Canvas (ddd-crew v1) — 경계 · 상태전이 · 불변식 · 명령/이벤트 · 처리량.</p>

    <div v-for="(a, i) in aggregates" :key="i" class="adc">
      <!-- Name -->
      <section class="adc__cell adc__name">
        <h5>Name</h5>
        <input v-model="a.name" placeholder="Aggregate" />
      </section>
      <!-- Description -->
      <section class="adc__cell adc__desc">
        <h5>Description</h5>
        <textarea :value="a.description || a.boundaryRationale" @input="a.description = $event.target.value" rows="4" placeholder="한 줄 책임 / 경계 근거" />
      </section>
      <!-- State Transitions -->
      <section class="adc__cell adc__state">
        <h5>State Transitions</h5>
        <div class="adc__states">
          <span v-for="(s, si) in (a.stateTransitions || [])" :key="si" class="adc__state-chip">
            {{ s.from }} <em>→{{ s.trigger }}→</em> {{ s.to }}
          </span>
        </div>
        <textarea :value="transitionText(a)" @input="setTransitions(a, $event)" rows="3"
                  placeholder="한 줄에 하나: From -> Trigger -> To" class="adc__state-edit" />
      </section>

      <!-- Throughput -->
      <section class="adc__cell adc__thru">
        <h5>Throughput</h5>
        <table class="adc__metrics">
          <thead><tr><th></th><th>AVG</th><th>MAX</th></tr></thead>
          <tbody>
            <tr v-for="m in THRU" :key="m.key">
              <td>{{ m.label }}</td>
              <td><input :value="mv(a,'throughput',m.key,'avg')" @input="setM(a,'throughput',m.key,'avg',$event)" /></td>
              <td><input :value="mv(a,'throughput',m.key,'max')" @input="setM(a,'throughput',m.key,'max',$event)" /></td>
            </tr>
          </tbody>
        </table>
      </section>
      <!-- Enforced Invariants -->
      <section class="adc__cell adc__inv">
        <h5>Enforced Invariants</h5>
        <textarea :value="(a.invariants||[]).join('\n')" @input="a.invariants = lines($event)" rows="4" placeholder="한 줄에 하나 (2개 이상)" />
        <span v-if="(a.invariants||[]).length < 2" class="adc__warn">불변식 2개 이상 권장</span>
      </section>
      <!-- Corrective Policies -->
      <section class="adc__cell adc__pol">
        <h5>Corrective Policies</h5>
        <textarea :value="(a.correctivePolicies||[]).join('\n')" @input="a.correctivePolicies = lines($event)" rows="4" placeholder="규칙 위반 시 보정 정책" />
      </section>

      <!-- Size -->
      <section class="adc__cell adc__size">
        <h5>Size</h5>
        <table class="adc__metrics">
          <thead><tr><th></th><th>AVG</th><th>MAX</th></tr></thead>
          <tbody>
            <tr v-for="m in SIZE" :key="m.key">
              <td>{{ m.label }}</td>
              <td><input :value="mv(a,'size',m.key,'avg')" @input="setM(a,'size',m.key,'avg',$event)" /></td>
              <td><input :value="mv(a,'size',m.key,'max')" @input="setM(a,'size',m.key,'max',$event)" /></td>
            </tr>
          </tbody>
        </table>
      </section>
      <!-- Handled Commands -->
      <section class="adc__cell adc__cmd">
        <h5>Handled Commands</h5>
        <div class="adc__chips">
          <span v-for="(c, ci) in (a.handledCommands||[])" :key="ci" class="adc__chip is-cmd">{{ c }}</span>
        </div>
        <textarea :value="(a.handledCommands||[]).join('\n')" @input="a.handledCommands = lines($event)" rows="2" placeholder="한 줄에 하나" />
      </section>
      <!-- Created Events -->
      <section class="adc__cell adc__evt">
        <h5>Created Events</h5>
        <div class="adc__chips">
          <span v-for="(e, ei) in (a.createdEvents||[])" :key="ei" class="adc__chip is-evt">{{ e }}</span>
        </div>
        <textarea :value="(a.createdEvents||[]).join('\n')" @input="a.createdEvents = lines($event)" rows="2" placeholder="한 줄에 하나" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const model = defineModel({ type: Object, required: true })
const aggregates = computed(() => model.value.aggregates || (model.value.aggregates = []))

const THRU = [
  { key: 'commandHandlingRate', label: 'Command Handling Rate' },
  { key: 'totalClients', label: 'Total Number of Clients' },
  { key: 'concurrencyConflictChance', label: 'Concurrency Conflict Chance' },
]
const SIZE = [
  { key: 'eventGrowthRate', label: 'Event Growth Rate' },
  { key: 'lifetime', label: 'Lifetime of a Single Instance' },
  { key: 'eventsPersisted', label: 'Number of Events Persisted' },
]

function lines(e) { return e.target.value.split('\n').map(s => s.trim()).filter(Boolean) }
function transitionText(a) {
  return (a.stateTransitions || []).map(s => `${s.from} -> ${s.trigger} -> ${s.to}`).join('\n')
}
function setTransitions(a, e) {
  a.stateTransitions = e.target.value.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const p = l.split('->').map(x => x.trim())
    return { from: p[0] || '', trigger: p[1] || '', to: p[2] || '' }
  })
}
function mv(a, group, key, col) { return ((a[group] || {})[key] || {})[col] || '' }
function setM(a, group, key, col, e) {
  if (!a[group]) a[group] = {}
  if (!a[group][key]) a[group][key] = {}
  a[group][key][col] = e.target.value
}
</script>

<style scoped>
.tviz__hint { font-size: 11px; color: var(--color-text-light); margin: 0 0 8px; }
.adc { border: 2px solid #2f3a4f; border-radius: 4px; margin-bottom: 16px; overflow: hidden;
  display: grid; grid-template-columns: 1.05fr 1fr 1fr;
  grid-template-areas:
    "name  state state"
    "desc  state state"
    "thru  inv   pol"
    "size  cmd   evt"; }
.adc__cell { padding: 8px 10px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); min-width: 0; }
.adc__cell h5 { margin: 0 0 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: var(--color-text-bright); }
.adc__cell textarea, .adc__cell input { width: 100%; box-sizing: border-box; font-size: 11px; padding: 3px 6px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); }
.adc__name { grid-area: name; }
.adc__desc { grid-area: desc; }
.adc__state { grid-area: state; }
.adc__thru { grid-area: thru; }
.adc__inv { grid-area: inv; }
.adc__pol { grid-area: pol; border-right: none; }
.adc__size { grid-area: size; border-bottom: none; }
.adc__cmd { grid-area: cmd; border-bottom: none; }
.adc__evt { grid-area: evt; border-right: none; border-bottom: none; }
.adc__states { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.adc__state-chip { font-size: 11px; background: var(--color-bg-tertiary); border-radius: 6px; padding: 2px 8px; }
.adc__state-chip em { color: var(--color-accent); font-style: normal; }
.adc__metrics { width: 100%; border-collapse: collapse; font-size: 10px; }
.adc__metrics th { text-align: left; font-size: 9px; color: var(--color-text-light); padding: 2px; }
.adc__metrics td { padding: 2px; }
.adc__metrics td:first-child { color: var(--color-text); }
.adc__metrics input { font-size: 10px; padding: 2px 4px; }
.adc__warn { font-size: 9px; color: var(--color-danger); }
.adc__chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.adc__chip { font-size: 10px; padding: 1px 6px; border-radius: 8px; }
.adc__chip.is-cmd { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.adc__chip.is-evt { background: #14532d; color: #bbf7d0; }
</style>
