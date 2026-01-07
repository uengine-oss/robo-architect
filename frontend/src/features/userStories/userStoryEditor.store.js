import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * User Story 편집 모달의 열림/닫힘 및 현재 편집 대상을 관리합니다.
 * (Navigator/Tree 등 다른 기능에서 "User Story 편집"을 트리거할 수 있도록)
 */
export const useUserStoryEditorStore = defineStore('userStoryEditor', () => {
  const isOpen = ref(false)
  const userStory = ref(null)

  function open(nextUserStory) {
    userStory.value = nextUserStory
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    userStory.value = null
  }

  return {
    isOpen,
    userStory,
    open,
    close
  }
})


