/**
 * OS-keychain-backed secret store (spec 023 D6 — `safeStorage`-only variant).
 *
 * Stores secrets as `safeStorage.encryptString` ciphertext written to
 * `<dataDir>/secrets/<id>.bin`. The ciphertext is bound to the OS user
 * via the platform keychain (macOS Keychain / Windows DPAPI / libsecret on
 * Linux when `--password-store=basic` isn't in effect). Without the user's
 * OS session the bytes on disk are useless.
 *
 * Why disk-backed + `safeStorage` and not the system keychain directly?
 *   - `safeStorage` is built into Electron 31 — no `keytar` native dep, no
 *     asarUnpack churn, no per-platform install pain.
 *   - The file location lives inside our existing per-user `<dataDir>`
 *     so reveal-logs / data-dir wipe also covers secrets.
 *
 * NEVER logged. Reads and writes log only the id, never the value, never
 * the file path beyond `~/` substitution (handled by callers).
 *
 * File mode (`<dataDir>/secrets/<id>.secret`, owner-only 0600): a packaged
 * macOS build is signed ad hoc — there is no Developer ID, so every new
 * version has a new code signature. The keychain then asks for the user's
 * password before the new version may read the key the previous version
 * stored, and a "Deny" leaves the app without the database password it set
 * up on first launch. So a packaged macOS app keeps its secrets (the local
 * database password, the bundled connection's password) in owner-only files
 * and never touches the keychain; development keeps `safeStorage`.
 * `ROBO_SECRET_STORE=file|keychain` overrides. An existing `<id>.bin` is
 * still read through `safeStorage`, so nothing stored before is lost.
 */

import { app, safeStorage } from "electron";
import fs from "node:fs";
import path from "node:path";

import { getDataDir } from "./data-dir";

const SECRETS_SUBDIR = "secrets";

function secretsDir(): string {
  return path.join(getDataDir(), SECRETS_SUBDIR);
}

function secretFile(id: string): string {
  validateId(id);
  return path.join(secretsDir(), `${id}.bin`);
}

function plainFile(id: string): string {
  validateId(id);
  return path.join(secretsDir(), `${id}.secret`);
}

function fileMode(): boolean {
  const forced = process.env.ROBO_SECRET_STORE;
  if (forced === "file") return true;
  if (forced === "keychain") return false;
  return app.isPackaged && process.platform === "darwin";
}

function validateId(id: string): void {
  // Defence-in-depth: refuse path traversal or anything that wouldn't be a
  // safe filename. SecretId is a closed enum in normal usage but this code
  // is also called with dynamic `connection.<uuid>.password` keys.
  if (!/^[A-Za-z0-9._-]+$/.test(id)) {
    throw new Error(`secret-store: invalid id ${JSON.stringify(id)}`);
  }
}

function ensureUsable(): void {
  if (!safeStorage.isEncryptionAvailable()) {
    // Surfaces a clear single failure mode rather than silently storing
    // plaintext. Callers can catch and degrade.
    throw new Error("secret-store: safeStorage encryption is unavailable on this host");
  }
}

export async function setSecret(id: string, value: string): Promise<void> {
  fs.mkdirSync(secretsDir(), { recursive: true, mode: 0o700 });
  if (fileMode()) {
    const file = plainFile(id);
    const temporary = `${file}.tmp`;
    await fs.promises.writeFile(temporary, value, { encoding: "utf8", mode: 0o600 });
    await fs.promises.rename(temporary, file);
    await unlinkIfPresent(secretFile(id)); // the file is the value now; a stale .bin must not win
    return;
  }
  ensureUsable();
  const cipher = safeStorage.encryptString(value);
  await fs.promises.writeFile(secretFile(id), cipher, { mode: 0o600 });
}

export async function getSecret(id: string): Promise<string | null> {
  try {
    return await fs.promises.readFile(plainFile(id), "utf8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") throw err;
  }
  let cipher: Buffer;
  try {
    cipher = await fs.promises.readFile(secretFile(id));
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
  ensureUsable();
  return safeStorage.decryptString(cipher);
}

async function unlinkIfPresent(file: string): Promise<void> {
  try {
    await fs.promises.unlink(file);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") throw err;
  }
}

export async function deleteSecret(id: string): Promise<void> {
  await unlinkIfPresent(secretFile(id));
  await unlinkIfPresent(plainFile(id));
}

export async function hasSecret(id: string): Promise<boolean> {
  for (const file of [plainFile(id), secretFile(id)]) {
    try {
      await fs.promises.access(file);
      return true;
    } catch {
      /* next */
    }
  }
  return false;
}

/**
 * Move the value at `oldId` to `newId`. No-op if `oldId` does not exist.
 * Used by the 023→v2 migration to re-key the legacy `neo4j.password` entry
 * to a per-SavedConnection `connection.<id>.password`.
 */
export async function rekeySecret(oldId: string, newId: string): Promise<boolean> {
  const value = await getSecret(oldId);
  if (value === null) return false;
  await setSecret(newId, value);
  await deleteSecret(oldId);
  return true;
}
