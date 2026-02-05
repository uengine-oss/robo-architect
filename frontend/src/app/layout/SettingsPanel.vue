<script setup>
import { ref } from 'vue'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useThemeStore } from '@/app/theme.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close'])

const terminologyStore = useTerminologyStore()
const themeStore = useThemeStore()
const canvasStore = useCanvasStore()

function handleBackdropClick(e) {
  if (e.target === e.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <Transition name="settings-panel">
    <div v-if="visible" class="settings-panel-backdrop" @click="handleBackdropClick">
      <div class="settings-panel" @click.stop>
        <div class="settings-panel__header">
          <h2 class="settings-panel__title">Settings</h2>
          <button class="settings-panel__close" @click="emit('close')" title="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="settings-panel__content">
          <!-- Theme Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Theme</h3>
              <span class="settings-section__description">Choose your preferred color scheme</span>
            </div>
            <div class="settings-section__control">
              <button 
                class="theme-option"
                :class="{ 'is-active': themeStore.theme === 'dark' }"
                @click="themeStore.setTheme('dark')"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
                <span>Dark</span>
              </button>
              <button 
                class="theme-option"
                :class="{ 'is-active': themeStore.theme === 'light' }"
                @click="themeStore.setTheme('light')"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="5"/>
                  <line x1="12" y1="1" x2="12" y2="3"/>
                  <line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/>
                  <line x1="21" y1="12" x2="23" y2="12"/>
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
                <span>Light</span>
              </button>
            </div>
          </div>

          <!-- Developer Terms Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Terminology</h3>
              <span class="settings-section__description">Switch between Event Storming and Developer terms</span>
            </div>
            <div class="settings-section__control">
              <div class="toggle-switch">
                <span class="toggle-switch__label">Developer Terms</span>
                <button 
                  class="toggle-switch__button"
                  :class="{ 'is-active': terminologyStore.developerMode }"
                  @click="terminologyStore.toggleDeveloperMode()"
                  :title="terminologyStore.developerMode ? 'Switch to Event Storming terms' : 'Switch to Developer terms'"
                >
                  <span class="toggle-switch__knob"></span>
                </button>
              </div>
            </div>
          </div>

          <!-- Design Level Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Design Level</h3>
              <span class="settings-section__description">Show or hide detailed fields in Design Viewer nodes</span>
            </div>
            <div class="settings-section__control">
              <div class="toggle-switch">
                <span class="toggle-switch__label">Show Fields</span>
                <button 
                  class="toggle-switch__button"
                  :class="{ 'is-active': canvasStore.showDesignLevel }"
                  @click="canvasStore.toggleDesignLevel()"
                  title="Toggle Design Level (Show/Hide Fields)"
                >
                  <span class="toggle-switch__knob"></span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.settings-panel-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.settings-panel {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  width: 90%;
  max-width: 480px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.settings-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.settings-panel__title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.settings-panel__close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
}

.settings-panel__close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.settings-panel__content {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-section__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-section__title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.settings-section__description {
  font-size: 0.8rem;
  color: var(--color-text-light);
}

.settings-section__control {
  display: flex;
  align-items: center;
}

/* Theme Options */
.theme-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  background: var(--color-bg-tertiary);
  border: 2px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.85rem;
  font-weight: 500;
}

.theme-option:first-child {
  margin-right: 8px;
}

.theme-option:hover {
  border-color: var(--color-accent);
  background: var(--color-bg-secondary);
}

.theme-option.is-active {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: white;
}

.theme-option svg {
  opacity: 0.8;
}

.theme-option.is-active svg {
  opacity: 1;
}

/* Toggle Switch */
.toggle-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.toggle-switch__label {
  font-size: 0.9rem;
  color: var(--color-text);
  font-weight: 500;
}

.toggle-switch__button {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.25s ease;
  padding: 0;
}

.toggle-switch__button:hover {
  border-color: var(--color-accent);
}

.toggle-switch__button.is-active {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-color: #059669;
}

.toggle-switch__knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  background: white;
  border-radius: 50%;
  transition: transform 0.25s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.toggle-switch__button.is-active .toggle-switch__knob {
  transform: translateX(20px);
}

/* Transitions */
.settings-panel-enter-active,
.settings-panel-leave-active {
  transition: opacity 0.2s ease;
}

.settings-panel-enter-active .settings-panel,
.settings-panel-leave-active .settings-panel {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.settings-panel-enter-from,
.settings-panel-leave-to {
  opacity: 0;
}

.settings-panel-enter-from .settings-panel,
.settings-panel-leave-to .settings-panel {
  transform: scale(0.95);
  opacity: 0;
}
</style>
