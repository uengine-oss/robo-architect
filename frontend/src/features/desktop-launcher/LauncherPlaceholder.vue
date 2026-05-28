<!--
  Spec 032 Phase 2 placeholder — replaced by `LauncherView.vue` in US tasks
  T027 / T030 / T041 / T047.

  Renders only when:
    - the renderer is running inside Electron (`session.isDesktop`)
    - AND the launcher hand-off has not happened yet (`!session.entered`)

  Until the real launcher lands this just shows a one-liner explaining
  what's missing and a single button that flips `session.entered = true`
  so a developer can punch through the gate manually during foundation-
  phase smoke runs (the button never ships to users — it's stripped by
  the real LauncherView replacement).
-->

<script setup>
import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'

const session = useSessionStore()

function bypass() {
  session.commitProfile({
    identity: {
      name: 'foundation-bypass',
      email: `bypass@${window.location.hostname || 'localhost'}`,
      source: 'unknown-fallback',
      displayName: 'foundation-bypass',
    },
    activeConnectionId: '',
    projectRoot: '',
  })
}
</script>

<template>
  <div class="launcher-placeholder">
    <h1>Desktop launcher (032)</h1>
    <p>
      Foundation phase complete — the launcher UI lands in user-story tasks
      <code>T027 / T039 / T041 / T046</code>. In the meantime the gate is
      live: real users cannot reach the main app until those tasks ship.
    </p>
    <button type="button" @click="bypass">
      Dev bypass — continue to the main app
    </button>
  </div>
</template>

<style scoped>
.launcher-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
  font-family: system-ui, sans-serif;
  text-align: center;
  gap: 1rem;
}
.launcher-placeholder h1 {
  margin: 0;
  font-size: 1.5rem;
}
.launcher-placeholder p {
  max-width: 36rem;
  color: #888;
}
.launcher-placeholder button {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid #888;
  background: transparent;
  color: inherit;
  cursor: pointer;
  border-radius: 4px;
}
.launcher-placeholder button:hover {
  background: rgba(255, 255, 255, 0.05);
}
</style>
