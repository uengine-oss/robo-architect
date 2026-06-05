<script setup>
import { onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

const props = defineProps({
  changeId: { type: String, required: true },
})

const store = useRequirementsStore()
const effects = ref([])
const loading = ref(false)

const labelIcon = {
  Aggregate: 'mdi-cube-outline',
  BoundedContext: 'mdi-domain',
  UserStory: 'mdi-account-outline',
}

onMounted(async () => {
  loading.value = true
  try {
    const data = await store.fetchImpact(props.changeId)
    effects.value = data.effects || []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="change-design-plan">
    <div class="text-caption font-weight-bold mb-2">설계 변경 계획</div>
    <v-progress-linear v-if="loading" indeterminate color="primary" />
    <div v-if="effects.length">
      <v-card
        v-for="e in effects"
        :key="e.nodeId"
        variant="outlined"
        class="mb-2 pa-2"
      >
        <div class="d-flex align-center gap-2">
          <v-icon size="small" :icon="labelIcon[e.nodeLabel] || 'mdi-circle-outline'" />
          <span class="text-caption font-weight-bold">{{ e.nodeId }}</span>
          <span class="text-caption">{{ e.nodeTitle }}</span>
        </div>
        <div class="text-caption text-grey mt-1">{{ e.reason }}</div>
      </v-card>
    </div>
    <div v-else-if="!loading" class="text-caption text-grey pa-3">
      설계 변경 대상이 없습니다.
    </div>
  </div>
</template>
