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
  
  return {
    theme,
    toggleTheme,
    setTheme,
    initTheme
  }
})
