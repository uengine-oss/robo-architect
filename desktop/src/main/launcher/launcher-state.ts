/**
 * In-memory launcher state machine (spec 032 T013).
 *
 * Tracks whether the launcher hand-off has happened. `enter` and `reopen`
 * are the only legal transitions; double-enter without an intervening
 * reopen is the LAUNCHER_ALREADY_ENTERED error in the IPC contract.
 *
 * The full `launcher:enter` and `launcher:reopen` handler bodies (settings
 * persistence, backend env swap, identity re-resolution) land in US1+US3
 * tasks T028, T048, T065. This module only exposes the state primitive +
 * a guard so other phases can call `assertPending()` / `markEntered()`.
 */

import type { LaunchProfile } from "../../shared/launcher-contract";

export type LauncherPhase = "pending" | "entered";

interface State {
  phase: LauncherPhase;
  /** The (connection, root) pair carried through enter. Null until entered. */
  activeProfile: LaunchProfile | null;
}

const _state: State = {
  phase: "pending",
  activeProfile: null,
};

export function currentPhase(): LauncherPhase {
  return _state.phase;
}

export function activeProfile(): LaunchProfile | null {
  return _state.activeProfile;
}

export function markEntered(profile: LaunchProfile): void {
  _state.phase = "entered";
  _state.activeProfile = profile;
}

export function markPending(): void {
  _state.phase = "pending";
  // We keep activeProfile populated through reopen so the launcher can
  // pre-select the user's current pair; the next enter overwrites it.
}

/**
 * Returns true iff a fresh `launcher:enter` is legal. Callers throw
 * `LAUNCHER_ALREADY_ENTERED` when this returns false.
 */
export function canEnter(): boolean {
  return _state.phase === "pending";
}

/** Test/teardown only. */
export function _resetForTests(): void {
  _state.phase = "pending";
  _state.activeProfile = null;
}
