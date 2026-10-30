import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // Theme: 'dark' | 'light'
  const theme = ref('dark')
  
  // Load theme from localStorage on init
  function initTheme() {
    try {
      const saved = localStorage.getItem('app_theme')
      if (saved === 'light' || saved === 'dark') {
        theme.value = saved
      } else {
        // Default to dark
        theme.value = 'dark'
      }
    } catch (e) {
      theme.value = 'dark'
    }
    applyTheme(theme.value)
  }
  
  // Apply theme to document
  function applyTheme(newTheme) {
    const root = document.documentElement
    if (newTheme === 'light') {
      root.classList.add('theme-light')
      root.classList.remove('theme-dark')
    } else {
      root.classList.add('theme-dark')
      root.classList.remove('theme-light')
    }
  }
  
  // Toggle theme
  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    applyTheme(theme.value)
    try {
      localStorage.setItem('app_theme', theme.value)
    } catch (e) {
      console.warn('Failed to save theme to localStorage:', e)
    }
  }
  
  // Set theme explicitly
  function setTheme(newTheme) {
    if (newTheme !== 'dark' && newTheme !== 'light') {
      console.warn('Invalid theme:', newTheme)
      return
    }
    theme.value = newTheme
    applyTheme(theme.value)
    try {
      localStorage.setItem('app_theme', theme.value)
    } catch (e) {
      console.warn('Failed to save theme to localStorage:', e)
    }
  }
  
  // Initialize on store creation
  initTheme()

  // 데스크톱 탭형 창 — 위쪽 탭 줄(셸)의 낮밤 단추나 다른 탭의 레일에서 바꾸면 같은 키(app_theme)가
  // 바뀐다. 그 변경을 받아 이 탭도 따라간다(storage 이벤트는 바꾼 쪽이 아닌 다른 문서에만 온다).
  window.addEventListener('storage', (e) => {
    if (e.key !== 'app_theme' || (e.newValue !== 'light' && e.newValue !== 'dark')) return
    theme.value = e.newValue
    applyTheme(theme.value)
  })
  
  return {
    theme,
    toggleTheme,
    setTheme,
    initTheme
  }
})
