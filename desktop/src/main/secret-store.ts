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
 */

import { safeStorage } from "electron";
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
  ensureUsable();
  fs.mkdirSync(secretsDir(), { recursive: true });
  const cipher = safeStorage.encryptString(value);
  await fs.promises.writeFile(secretFile(id), cipher, { mode: 0o600 });
}

export async function getSecret(id: string): Promise<string | null> {
  ensureUsable();
  try {
    const cipher = await fs.promises.readFile(secretFile(id));
    return safeStorage.decryptString(cipher);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
}

export async function deleteSecret(id: string): Promise<void> {
  try {
    await fs.promises.unlink(secretFile(id));
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") throw err;
  }
}

export async function hasSecret(id: string): Promise<boolean> {
  try {
    await fs.promises.access(secretFile(id));
    return true;
  } catch {
    return false;
  }
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
