/**
 * Project-root handlers (spec 032 T034 / T035 / T036).
 *
 *   chooseProjectRoot()  — opens native folder dialog, returns
 *                          {path, valid, basename, parent} or {cancelled:true}
 *   validateProjectRoot(path) — exists + readable + isDirectory check
 *   listRecentProjectRoots()  — reads recentProjectRoots from settings,
 *                          zipped with lastUsedAt (lastProfile.enteredAt
 *                          when the path matches, else null)
 *   pushRecentProjectRoot(path) — dedupe + prepend + truncate to 5
 *
 * No `BrowserWindow` parameter — the dialog is opened modally against
 * the currently-focused window. This avoids passing window references
 * through the IPC layer (callers just invoke through the bridge).
 */

import { BrowserWindow, dialog } from "electron";
import fs from "node:fs";
import path from "node:path";

import { IpcErrorCodes } from "../../shared/ipc-contract";
import type {
  ProjectRootChooseResult,
  ProjectRootEntry,
  ProjectRootValidateResult,
} from "../../shared/launcher-contract";
import { IpcHandlerError } from "../ipc";

import { loadSettings, saveSettings } from "../settings";

const MAX_RECENT = 5;

export async function chooseProjectRoot(): Promise<ProjectRootChooseResult> {
  const focused = BrowserWindow.getFocusedWindow();
  const result = focused
    ? await dialog.showOpenDialog(focused, {
        properties: ["openDirectory", "dontAddToRecent"],
      })
    : await dialog.showOpenDialog({
        properties: ["openDirectory", "dontAddToRecent"],
      });

  if (result.canceled || result.filePaths.length === 0) {
    return { cancelled: true };
  }

  const picked = result.filePaths[0]!;
  const validation = await validateProjectRoot(picked);
  return {
    path: picked,
    valid: validation.valid,
    basename: path.basename(picked),
    parent: path.dirname(picked),
  };
}

export async function validateProjectRoot(p: string): Promise<ProjectRootValidateResult> {
  if (typeof p !== "string" || p.length === 0 || !path.isAbsolute(p)) {
    return { valid: false, reason: "not-found" };
  }
  let stat: fs.Stats;
  try {
    stat = await fs.promises.stat(p);
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return { valid: false, reason: "not-found" };
    return { valid: false, reason: "unreadable" };
  }
  if (!stat.isDirectory()) {
    return { valid: false, reason: "not-a-directory" };
  }
  try {
    await fs.promises.access(p, fs.constants.R_OK);
  } catch {
    return { valid: false, reason: "unreadable" };
  }
  return { valid: true };
}

export async function listRecentProjectRoots(): Promise<ProjectRootEntry[]> {
  const settings = await loadSettings();
  return settings.recentProjectRoots.map((p) => ({
    path: p,
    // Only the last-used pair carries a precise timestamp; older entries
    // get a null (renderer treats null as "older than last").
    lastUsedAt:
      settings.lastProfile && settings.lastProfile.projectRoot === p
        ? settings.lastProfile.enteredAt
        : new Date(0).toISOString(),
  }));
}

/**
 * Create a new directory at the given absolute path and return its info.
 * Rejects with PROJECT_ROOT_INVALID when the path is already taken or
 * the parent directory does not exist.
 */
export async function createProjectRoot(absolutePath: string): Promise<ProjectRootChooseResult> {
  if (typeof absolutePath !== "string" || !path.isAbsolute(absolutePath)) {
    throw new IpcHandlerError(IpcErrorCodes.PROJECT_ROOT_INVALID, "path must be absolute");
  }
  try {
    await fs.promises.mkdir(absolutePath, { recursive: false });
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "EEXIST") {
      throw new IpcHandlerError(IpcErrorCodes.PROJECT_ROOT_INVALID, "folder already exists");
    }
    if (code === "ENOENT") {
      throw new IpcHandlerError(IpcErrorCodes.PROJECT_ROOT_INVALID, "parent directory does not exist");
    }
    throw new IpcHandlerError(
      IpcErrorCodes.PROJECT_ROOT_INVALID,
      `could not create folder: ${(err as Error).message}`,
    );
  }
  return {
    path: absolutePath,
    valid: true,
    basename: path.basename(absolutePath),
    parent: path.dirname(absolutePath),
  };
}

/**
 * Used by `launcher:enter` to record a successful hand-off.
 * Deduplicates the path (case-sensitive — matches platform filesystem
 * semantics on macOS by default and on Windows we use the OS-normalised
 * form `path.resolve` returned), prepends, and caps at MAX_RECENT.
 */
export async function pushRecentProjectRoot(rawPath: string): Promise<void> {
  const settings = await loadSettings();
  const normalised = path.resolve(rawPath);
  const next = [normalised, ...settings.recentProjectRoots.filter((p) => p !== normalised)];
  settings.recentProjectRoots = next.slice(0, MAX_RECENT);
  await saveSettings(settings);
}
