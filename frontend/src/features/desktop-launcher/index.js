// 032 desktop launcher — Vue feature barrel.
//
// Components and stores added incrementally per /specs/032-desktop-startup-picker/tasks.md.
// Re-exports follow as tasks land (T017/T018 stores, T026 ConnectionList, T027 LauncherView, …).

export { useSessionStore } from './stores/session-store.js'
export { useLauncherStore } from './stores/launcher-store.js'
