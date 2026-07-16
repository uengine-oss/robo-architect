<template>
  <!-- spec 052: 레거시 참조 프로버넌스 칩 — 여정 전 표면 공용(사본 금지). 참조 0건이면 미렌더. -->
  <span v-if="totalNodes > 0" class="lref-wrap" @keydown.esc="open = false">
    <button
      class="lref-chip"
      :class="{ open }"
      :title="`이 제안은 레거시 분석 그래프에서 함수 ${totalNodes}개를 참조해 생성됨`"
      @click.stop="open = !open"
    >
      ⛓ 레거시 근거 <b>{{ totalNodes }}</b>
    </button>
    <div v-if="open" class="lref-pop" @click.stop>
      <div v-for="(st, i) in refs" :key="i" class="lref-stage">
        <div v-for="(r, j) in st.retrieves" :key="j" class="lref-retrieve">
          <div class="lref-q">
            <span class="lref-stagename">{{ st.stage }}</span>
            검색: <code>“{{ r.query || '(질의 미기록)' }}”</code>
            <span class="lref-at">{{ shortAt(r.at) }}</span>
          </div>
          <div v-for="n in r.nodes" :key="n.id" class="lref-node">
            <span class="lref-fn">{{ n.name }}<i v-if="n.label === 'TABLE'"> TABLE</i></span>
            <span class="lref-sum">{{ n.summary }}</span>
            <span v-if="n.rulesCount" class="lref-rules">규칙 {{ n.rulesCount }}</span>
          </div>
        </div>
      </div>
    </div>
  </span>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  /** proposal.legacyReferences — [{stage, retrieves:[{query, nodes:[{id,name,label,summary,relevance,rulesCount}], at}]}] */
  refs: { type: Array, default: () => [] },
})

const open = ref(false)
const totalNodes = computed(() =>
  (props.refs || []).reduce(
    (a, st) => a + (st.retrieves || []).reduce((b, r) => b + (r.nodes || []).length, 0), 0))

function shortAt(at) {
  if (!at) return ''
  const m = String(at).match(/T(\d{2}:\d{2})/)
  return m ? m[1] : ''
}
function closeOnOutside() { open.value = false }
onMounted(() => document.addEventListener('click', closeOnOutside))
onBeforeUnmount(() => document.removeEventListener('click', closeOnOutside))
</script>

<style scoped>
.lref-wrap { position: relative; display: inline-flex; }
.lref-chip {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(125, 139, 245, 0.10); border: 1px solid rgba(125, 139, 245, 0.45);
  color: #aab4f0; border-radius: 999px; padding: 2px 11px; font-size: 12px;
  cursor: pointer; line-height: 1.6; white-space: nowrap;
}
.lref-chip:hover, .lref-chip.open { border-color: #7d8bf5; background: rgba(125, 139, 245, 0.18); }
.lref-chip b { color: #7d8bf5; }
.lref-pop {
  /* 칩이 화면 좌측에 있을 때 오른쪽으로 펼쳐야 목록 패널에 안 가린다(실측 결함).
     z-index 는 목록 패널·헤더보다 위로. */
  position: absolute; left: 0; top: calc(100% + 8px); z-index: 1000; width: 440px; max-height: 340px;
  overflow-y: auto; background: #20242f; border: 1px solid #3a4468; border-radius: 10px;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5); padding: 10px 12px; text-align: left;
}
.lref-q { color: #8b93a7; font-size: 12px; margin: 6px 0 4px; }
.lref-q code { color: #cdd4f7; background: #171a22; padding: 1px 6px; border-radius: 4px; }
.lref-stagename {
  font-size: 10px; letter-spacing: 1px; color: #7d8bf5; border: 1px solid #3a4468;
  border-radius: 4px; padding: 0 5px; margin-right: 6px;
}
.lref-at { float: right; color: #5b6274; font-size: 11px; }
.lref-node { display: flex; align-items: baseline; gap: 8px; padding: 5px 6px; border-radius: 6px; }
.lref-node:hover { background: #262c3a; }
.lref-fn { font-family: Consolas, monospace; color: #cdd4f7; font-size: 12.5px; white-space: nowrap; }
.lref-fn i { color: #6e7790; font-size: 10px; font-style: normal; }
.lref-sum { color: #8b93a7; font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lref-rules { color: #7d8bf5; font-size: 11px; white-space: nowrap; }
</style>
