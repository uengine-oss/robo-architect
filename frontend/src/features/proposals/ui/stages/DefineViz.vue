<template>
  <div class="dfviz">
    <p class="dfviz__hint">Bounded Context Canvas (ddd-crew v5) — 각 영향 BC 의 책임·분류·통신·언어·결정.</p>

    <div v-if="contexts.length > 1" class="dfviz__tabs">
      <button
        v-for="(c, i) in contexts"
        :key="c.name || i"
        type="button"
        :class="['dfviz__tab', { 'is-active': i === activeContextIndex }]"
        @click="activeContextIndex = i"
      >
        {{ c.name || `BC ${i + 1}` }}
      </button>
    </div>

    <div v-if="currentContext" class="bcc">
      <div class="bcc__name">
        <span class="bcc__label">Name</span>
        <input class="bcc__name-in" v-model="currentContext.name" placeholder="컨텍스트 이름" />
        <span class="bcc__src">github.com/ddd-crew/bounded-context-canvas · V5</span>
      </div>

      <section class="bcc__cell bcc__purpose">
        <h5>Purpose</h5>
        <textarea v-model="currentContext.purpose" rows="3" placeholder="비즈니스 관점의 책임/제공 가치" />
      </section>

      <section class="bcc__cell bcc__strat">
        <h5>Strategic Classification</h5>
        <div class="bcc__strat-cols">
          <div>
            <span class="bcc__sub">Domain</span>
            <label v-for="d in DOMAINS" :key="d" class="bcc__opt">
              <input type="radio" :name="`dom${activeContextIndex}`" :value="d" :checked="currentContext.classification === d" @change="currentContext.classification = d" /> {{ d.toLowerCase() }}
            </label>
          </div>
          <div>
            <span class="bcc__sub">Business Model</span>
            <label v-for="b in BIZ" :key="b" class="bcc__opt">
              <input type="checkbox" :checked="(currentContext.businessModel || []).includes(b)" @change="toggle(currentContext, 'businessModel', b)" /> {{ b.replace('_',' ') }}
            </label>
          </div>
          <div>
            <span class="bcc__sub">Evolution</span>
            <label v-for="e in EVO" :key="e" class="bcc__opt">
              <input type="radio" :name="`evo${activeContextIndex}`" :value="e" :checked="currentContext.evolution === e" @change="currentContext.evolution = e" /> {{ e.replace('_',' ') }}
            </label>
          </div>
        </div>
      </section>

      <section class="bcc__cell bcc__roles">
        <h5>Domain Roles</h5>
        <label v-for="r in ROLES" :key="r" class="bcc__opt">
          <input type="checkbox" :checked="(currentContext.domainRoles || []).includes(r)" @change="toggle(currentContext, 'domainRoles', r)" /> {{ r }} context
        </label>
      </section>

      <section class="bcc__cell bcc__inbound">
        <h5>Inbound Communication</h5>
        <div class="bcc__msg-head"><span>Collaborator</span><span>Message</span></div>
        <div v-for="(m, mi) in (currentContext.inbound || [])" :key="mi" class="bcc__msg">
          <input class="bcc__msg-col" :value="m.collaborator || m.from" @input="m.collaborator = $event.target.value" placeholder="collaborator" />
          <input class="bcc__msg-name" v-model="m.message" placeholder="message" />
          <select class="bcc__msg-type" :class="typeClass(m.type)" v-model="m.type">
            <option>Query</option><option>Command</option><option>Event</option>
          </select>
        </div>
        <span class="bcc__arrow">→</span>
      </section>

      <section class="bcc__cell bcc__center">
        <h5>Ubiquitous Language</h5>
        <div class="bcc__sub2">Context-specific domain terminology</div>
        <div v-for="(u, ui) in (currentContext.ubiquitousLanguage || [])" :key="ui" class="bcc__term">
          <input class="bcc__term-t" v-model="u.term" placeholder="Domain Term" />
          <input class="bcc__term-d" v-model="u.definition" placeholder="definition" />
        </div>
        <span v-if="(currentContext.ubiquitousLanguage || []).length < 5" class="bcc__warn">용어 5개 이상 권장</span>

        <h5 class="bcc__mt">Business Decisions</h5>
        <div class="bcc__sub2">Key business rules, policies, and decisions</div>
        <textarea :value="(currentContext.businessDecisions || []).join('\n')" @input="currentContext.businessDecisions = lines($event)" rows="3" placeholder="한 줄에 하나" />

        <template v-if="currentContext.languageClashes?.length">
          <h5 class="bcc__mt bcc__clash">⚠️ Language Clashes</h5>
          <ul><li v-for="(l, li) in currentContext.languageClashes" :key="li">{{ l }}</li></ul>
        </template>
      </section>

      <section class="bcc__cell bcc__outbound">
        <h5>Outbound Communication</h5>
        <div class="bcc__msg-head"><span>Message</span><span>Collaborator</span></div>
        <div v-for="(m, mi) in (currentContext.outbound || [])" :key="mi" class="bcc__msg">
          <input class="bcc__msg-name" v-model="m.message" placeholder="message" />
          <select class="bcc__msg-type" :class="typeClass(m.type)" v-model="m.type">
            <option>Query</option><option>Command</option><option>Event</option>
          </select>
          <input class="bcc__msg-col" :value="m.collaborator || m.to" @input="m.collaborator = $event.target.value" placeholder="collaborator" />
        </div>
        <span class="bcc__arrow">→</span>
      </section>

      <section class="bcc__cell bcc__assume">
        <h5>Assumptions</h5>
        <textarea :value="(currentContext.assumptions || []).join('\n')" @input="currentContext.assumptions = lines($event)" rows="3" placeholder="검증되지 않은 설계 가정 (한 줄에 하나)" />
      </section>

      <section class="bcc__cell bcc__metrics">
        <h5>Verification Metrics</h5>
        <textarea :value="(currentContext.verificationMetrics || []).join('\n')" @input="currentContext.verificationMetrics = lines($event)" rows="3" placeholder="구조를 (in)validate 할 지표 (한 줄에 하나)" />
      </section>

      <section class="bcc__cell bcc__questions">
        <h5>Open Questions</h5>
        <textarea :value="(currentContext.openQuestions || []).join('\n')" @input="currentContext.openQuestions = lines($event)" rows="3" placeholder="미해결 질문 (한 줄에 하나)" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const model = defineModel({ type: Object, required: true })
const activeContextIndex = ref(0)
const contexts = computed(() => model.value.contexts || (model.value.contexts = []))
const currentContext = computed(() => contexts.value[activeContextIndex.value] || contexts.value[0] || null)

watch(() => contexts.value.length, (len) => {
  if (activeContextIndex.value >= len) activeContextIndex.value = Math.max(0, len - 1)
})

const DOMAINS = ['CORE', 'SUPPORTING', 'GENERIC', 'OTHER']
const BIZ = ['revenue', 'engagement', 'compliance', 'cost_reduction']
const EVO = ['genesis', 'custom_built', 'product', 'commodity']
const ROLES = ['draft', 'execution', 'analysis', 'gateway', 'other']

function toggle(c, key, val) {
  if (!Array.isArray(c[key])) c[key] = []
  const idx = c[key].indexOf(val)
  if (idx >= 0) c[key].splice(idx, 1); else c[key].push(val)
}
function lines(e) { return e.target.value.split('\n').map(s => s.trim()).filter(Boolean) }
function typeClass(t) { return 'is-' + (t || '').toLowerCase() }
</script>

<style scoped>
.dfviz__hint { font-size: 11px; color: var(--color-text-light); margin: 0 0 8px; }
.dfviz__tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px; }
.dfviz__tab { border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-bg-secondary); color: var(--color-text); font-size: 12px; padding: 4px 12px; cursor: pointer; }
.dfviz__tab.is-active { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
.bcc { border: 2px solid var(--color-text); border-radius: 4px; margin-bottom: 16px; overflow: hidden;
  display: grid; grid-template-columns: 1.05fr 1.25fr 1fr;
  grid-template-areas:
    "name name name"
    "purpose strat roles"
    "inbound center outbound"
    "assume metrics questions"; }
.bcc__name { grid-area: name; display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 2px solid var(--color-text); }
.bcc__label { font-size: 15px; font-weight: 700; color: var(--color-text-bright); }
.bcc__name-in { flex: 1; font-size: 14px; font-weight: 600; border: none; border-bottom: 1px solid var(--color-border); background: transparent; color: var(--color-text-bright); }
.bcc__src { font-size: 9px; color: var(--color-text-light); }
.bcc__cell { padding: 8px 10px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); min-width: 0; }
.bcc__cell h5 { margin: 0 0 4px; font-size: 13px; font-weight: 700; color: var(--color-text-bright); }
.bcc__cell h5.bcc__mt { margin-top: 10px; }
.bcc__cell textarea, .bcc__cell input { width: 100%; box-sizing: border-box; font-size: 11px; padding: 3px 6px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); }
.bcc__purpose { grid-area: purpose; }
.bcc__strat { grid-area: strat; }
.bcc__roles { grid-area: roles; border-right: none; }
.bcc__inbound { grid-area: inbound; position: relative; }
.bcc__center { grid-area: center; background: var(--color-bg-secondary); }
.bcc__outbound { grid-area: outbound; position: relative; border-right: none; }
.bcc__assume { grid-area: assume; border-bottom: none; }
.bcc__metrics { grid-area: metrics; border-bottom: none; }
.bcc__questions { grid-area: questions; border-right: none; border-bottom: none; }
.bcc__strat-cols { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
.bcc__sub { display: block; font-size: 10px; font-weight: 700; color: var(--color-text-light); margin-bottom: 2px; }
.bcc__sub2 { font-size: 10px; color: var(--color-text-light); margin-bottom: 4px; }
.bcc__opt { display: block; font-size: 10px; color: var(--color-text); margin: 1px 0; white-space: nowrap; }
.bcc__opt input { width: auto !important; margin-right: 3px; }
.bcc__msg-head { display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-light); margin-bottom: 3px; }
.bcc__msg { display: flex; gap: 3px; margin-bottom: 3px; align-items: center; }
.bcc__msg-col { flex: 1; }
.bcc__msg-name { flex: 1.4; }
.bcc__msg-type { width: 78px !important; flex: none; border-width: 2px !important; }
.bcc__msg-type.is-query { border-color: #84cc16 !important; }
.bcc__msg-type.is-command { border-color: #60a5fa !important; }
.bcc__msg-type.is-event { border-color: #fbbf24 !important; }
.bcc__arrow { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); color: var(--color-border); font-size: 18px; }
.bcc__term { display: flex; gap: 3px; margin-bottom: 3px; }
.bcc__term-t { flex: 0.8; font-weight: 600; }
.bcc__term-d { flex: 1.5; }
.bcc__warn { font-size: 9px; color: var(--color-danger); }
.bcc__clash { color: var(--color-danger); }
.bcc__center ul { margin: 0; padding-left: 16px; font-size: 11px; }
</style>
