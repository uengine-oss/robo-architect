/**
 * 014 analysis-scope-browser: local filesystem browse handlers.
 *
 *   listDir({root, path})  — 그 폴더의 즉시 자식(파일/폴더) 목록. 지연 로딩(펼칠 때마다).
 *   readFile({root, path}) — 파일 텍스트 미리보기. 바이너리/초대형은 렌더 안 함.
 *
 * 보안: 모든 경로는 root 하위로 한정(경로 탈출 `..`·절대경로 우회 차단). 심볼릭 링크는
 * 따라가지 않는다(순환 확장 차단, spec Edge). 접근불가/없음은 throw → ipc 봉투가 에러로 변환.
 */

import fs from "node:fs";
import path from "node:path";

import { shell } from "electron";

import { IpcErrorCodes } from "../shared/ipc-contract";
import type {
  FsEntry,
  FsListInput,
  FsMovePairInput,
  FsPathInput,
  FsReadInput,
  FsReadResult,
  FsStageProjectInput,
  FsStageProjectResult,
  FsWriteInput,
} from "../shared/fs-browser-contract";
import { IpcHandlerError } from "./ipc";

/** 텍스트 미리보기 상한 — 초과 파일은 렌더하지 않고 안내. */
const MAX_PREVIEW_BYTES = 512 * 1024;
const MAX_PROJECT_FILES = 20_000;
const MAX_PROJECT_BYTES = 256 * 1024 * 1024;
const MAX_SINGLE_FILE_BYTES = 100 * 1024 * 1024;
const EXCLUDED_INGRESS_DIRECTORIES = new Set([
  ".git",
  ".idea",
  ".mypy_cache",
  ".pytest_cache",
  ".robo",
  ".ruff_cache",
  ".svn",
  ".venv",
  ".vscode",
  "__pycache__",
  "build",
  "dist",
  "node_modules",
  "out",
  "target",
  "venv",
]);

interface ProjectIngressFile {
  absolutePath: string;
  relativePath: string;
  size: number;
}

interface ParserUploadSummary {
  files?: unknown[];
  ddlFiles?: unknown[];
  nontargetFiles?: unknown[];
}

/** path 가 root 자신이거나 그 하위인지 검증 — 위반 시 throw. 정규화된 절대경로 반환. */
function resolveWithinRoot(root: string, target: string): string {
  if (typeof root !== "string" || !path.isAbsolute(root)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "root must be an absolute path");
  }
  if (typeof target !== "string" || !path.isAbsolute(target)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "path must be an absolute path");
  }
  const nRoot = path.resolve(root);
  const nTarget = path.resolve(target);
  if (nTarget !== nRoot && !nTarget.startsWith(nRoot + path.sep)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "path escapes the analysis root");
  }
  return nTarget;
}

export async function listDir({ root, path: dir }: FsListInput): Promise<FsEntry[]> {
  const target = resolveWithinRoot(root, dir);

  let dirents: fs.Dirent[];
  try {
    dirents = await fs.promises.readdir(target, { withFileTypes: true });
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") {
      throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "directory not found");
    }
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "directory unreadable");
  }

  const entries: FsEntry[] = [];
  for (const d of dirents) {
    // 심볼릭 링크/특수파일은 제외 — 일반 폴더·파일만(순환 확장 방지).
    const isDir = d.isDirectory();
    const isFile = d.isFile();
    if (!isDir && !isFile) continue;

    const full = path.join(target, d.name);
    const entry: FsEntry = { name: d.name, path: full, type: isDir ? "dir" : "file" };
    if (isFile) {
      try {
        entry.size = (await fs.promises.stat(full)).size;
      } catch {
        /* 접근불가 파일은 size 생략 — 목록엔 남긴다 */
      }
    }
    entries.push(entry);
  }

  // 폴더 먼저 → 파일, 각 그룹 이름순(대소문자 무관).
  entries.sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  });
  return entries;
}

export async function readFile({ root, path: file }: FsReadInput): Promise<FsReadResult> {
  const target = resolveWithinRoot(root, file);

  let stat: fs.Stats;
  try {
    stat = await fs.promises.stat(target);
  } catch {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "file not found or unreadable");
  }
  if (!stat.isFile()) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "not a file");
  }
  if (stat.size > MAX_PREVIEW_BYTES) {
    return { kind: "too-large", size: stat.size };
  }

  const buf = await fs.promises.readFile(target);
  // 앞부분에 NUL 바이트가 있으면 바이너리로 간주 — 렌더하지 않는다.
  const sample = buf.subarray(0, Math.min(buf.length, 8192));
  if (sample.includes(0)) {
    return { kind: "binary" };
  }
  return { kind: "text", content: buf.toString("utf8") };
}

async function collectProjectIngressFiles(
  root: string,
): Promise<{ files: ProjectIngressFile[]; skippedEntryCount: number; totalBytes: number }> {
  const resolvedRoot = resolveWithinRoot(root, root);
  const rootStat = await fs.promises.stat(resolvedRoot).catch(() => null);
  if (!rootStat?.isDirectory()) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "analysis root is not a readable directory");
  }

  const files: ProjectIngressFile[] = [];
  let skippedEntryCount = 0;
  let totalBytes = 0;
  const pending = [resolvedRoot];
  while (pending.length > 0) {
    const directory = pending.pop()!;
    const entries = await fs.promises.readdir(directory, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
    for (const entry of entries) {
      const absolutePath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        if (EXCLUDED_INGRESS_DIRECTORIES.has(entry.name.toLowerCase())) {
          skippedEntryCount += 1;
        } else {
          pending.push(absolutePath);
        }
        continue;
      }
      if (!entry.isFile()) {
        skippedEntryCount += 1;
        continue;
      }
      const stat = await fs.promises.stat(absolutePath);
      if (stat.size > MAX_SINGLE_FILE_BYTES) {
        throw new IpcHandlerError(
          IpcErrorCodes.VALIDATION,
          `project file exceeds ${MAX_SINGLE_FILE_BYTES} bytes: ${entry.name}`,
        );
      }
      const relativePath = path.relative(resolvedRoot, absolutePath).split(path.sep).join("/");
      totalBytes += stat.size;
      files.push({ absolutePath, relativePath, size: stat.size });
      if (files.length > MAX_PROJECT_FILES || totalBytes > MAX_PROJECT_BYTES) {
        throw new IpcHandlerError(
          IpcErrorCodes.VALIDATION,
          `project ingress limit exceeded: files=${files.length} bytes=${totalBytes}`,
        );
      }
    }
  }
  if (files.length === 0) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "analysis root contains no files");
  }
  files.sort((a, b) => a.relativePath.localeCompare(b.relativePath));
  return { files, skippedEntryCount, totalBytes };
}

/**
 * Windows host 폴더를 Parser의 canonical upload ingress로 반입한다.
 *
 * Linux container가 Windows 절대경로를 직접 읽게 하지 않는다. Electron main만 host
 * filesystem을 읽고 상대경로를 보존한 multipart를 app-owned Gateway로 보낸다.
 * DDL/source 판정은 Parser의 content classifier가 계속 단일 진실이다.
 */
export async function stageProject({
  root,
}: FsStageProjectInput): Promise<FsStageProjectResult> {
  const gateway = process.env.ROBO_GATEWAY_URL;
  if (!gateway) {
    throw new IpcHandlerError(IpcErrorCodes.INTERNAL, "Gateway is not ready");
  }
  let gatewayUrl: URL;
  try {
    gatewayUrl = new URL(gateway);
  } catch {
    throw new IpcHandlerError(IpcErrorCodes.INTERNAL, "Gateway URL is invalid");
  }
  if (
    gatewayUrl.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "::1", "[::1]"].includes(gatewayUrl.hostname)
  ) {
    throw new IpcHandlerError(IpcErrorCodes.INTERNAL, "Gateway must be loopback-only");
  }

  const collected = await collectProjectIngressFiles(root);
  const form = new FormData();
  for (const file of collected.files) {
    const bytes = await fs.promises.readFile(file.absolutePath);
    form.append("files", new Blob([bytes]), file.relativePath);
  }

  const endpoint = new URL("/antlr/fileUpload", gatewayUrl);
  const response = await fetch(endpoint, { method: "POST", body: form });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 2_000);
    throw new IpcHandlerError(
      IpcErrorCodes.INTERNAL,
      `Parser project ingress failed: HTTP ${response.status}: ${detail}`,
    );
  }
  const summary = (await response.json()) as ParserUploadSummary;
  return {
    fileCount: collected.files.length,
    sourceCount: Array.isArray(summary.files) ? summary.files.length : 0,
    ddlCount: Array.isArray(summary.ddlFiles) ? summary.ddlFiles.length : 0,
    nontargetCount: Array.isArray(summary.nontargetFiles) ? summary.nontargetFiles.length : 0,
    skippedEntryCount: collected.skippedEntryCount,
    totalBytes: collected.totalBytes,
  };
}

// ---------------------------------------------------------------------------
// 파일 작업 — 전부 root 하위 한정. 사용자 디스크를 실제로 바꾸므로 신중.
// ---------------------------------------------------------------------------

/** 이동/이름변경 — from·to 모두 root 하위. */
export async function rename({ root, from, to }: FsMovePairInput): Promise<{ ok: true }> {
  const src = resolveWithinRoot(root, from);
  const dst = resolveWithinRoot(root, to);
  try {
    await fs.promises.rename(src, dst);
  } catch (err) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `이동/이름변경 실패: ${(err as Error).message}`);
  }
  return { ok: true };
}

/** 복사 — 폴더면 재귀 복사. from·to 모두 root 하위. */
export async function copy({ root, from, to }: FsMovePairInput): Promise<{ ok: true }> {
  const src = resolveWithinRoot(root, from);
  const dst = resolveWithinRoot(root, to);
  try {
    await fs.promises.cp(src, dst, { recursive: true, errorOnExist: true, force: false });
  } catch (err) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `복사 실패: ${(err as Error).message}`);
  }
  return { ok: true };
}

/** 삭제 — 영구삭제가 아니라 OS 휴지통으로 보낸다(복구 가능). */
export async function trash({ root, path: target }: FsPathInput): Promise<{ ok: true }> {
  const abs = resolveWithinRoot(root, target);
  if (abs === path.resolve(root)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "분석 루트 자체는 삭제할 수 없습니다");
  }
  try {
    await shell.trashItem(abs);
  } catch (err) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `삭제 실패: ${(err as Error).message}`);
  }
  return { ok: true };
}

/** 파일 텍스트 저장(덮어쓰기). path 는 root 하위. 폴더엔 못 쓴다. */
export async function writeFile({ root, path: target, content }: FsWriteInput): Promise<{ ok: true }> {
  const abs = resolveWithinRoot(root, target);
  const stat = await fs.promises.stat(abs).catch(() => null);
  if (stat && stat.isDirectory()) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "폴더에는 저장할 수 없습니다");
  }
  try {
    await fs.promises.writeFile(abs, content, "utf8");
  } catch (err) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `저장 실패: ${(err as Error).message}`);
  }
  return { ok: true };
}

/** 새 폴더 생성. path 는 만들 폴더의 절대경로(root 하위). */
export async function mkdir({ root, path: target }: FsPathInput): Promise<{ ok: true }> {
  const abs = resolveWithinRoot(root, target);
  try {
    await fs.promises.mkdir(abs, { recursive: false });
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "EEXIST") {
      throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "이미 같은 이름이 있습니다");
    }
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `새 폴더 실패: ${(err as Error).message}`);
  }
  return { ok: true };
}
