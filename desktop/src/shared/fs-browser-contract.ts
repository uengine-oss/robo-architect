/**
 * 014 analysis-scope-browser: local filesystem browse surface (main ↔ renderer).
 *
 * 경로 모드(Electron 임베드)에서 analyzer 입력 UI 가 로컬 폴더 트리를 보여주고
 * 파일을 미리보기 위한 최소 FS 접근. 렌더러는 디스크를 직접 못 읽으므로 호스트(IPC) 경유.
 *
 * 보안: 모든 호출은 `{ root, path }` 를 받고, path 는 반드시 root 하위로 한정한다
 * (경로 탈출 차단). root/path 는 절대경로. 자세한 검증은 main/fs-browser.ts.
 *
 * launcher-contract.ts 와 동일하게 IpcRequestMap·DesktopBridge 를 declaration merging 으로
 * 증강한다(ipc-contract.ts 무수정).
 */

import type { IpcResult } from "./ipc-contract";

// ---------------------------------------------------------------------------
// Entities (spec 014 §Key Entities — Source Tree Node / File Preview)
// ---------------------------------------------------------------------------

/** 트리의 한 항목 — 루트 아래의 파일/폴더 1개(즉시 자식만, 지연 로딩). */
export interface FsEntry {
  /** 표시 이름(basename). */
  name: string;
  /** 절대경로. 이후 listDir/readFile 의 path 인자로 그대로 쓴다. */
  path: string;
  type: "file" | "dir";
  /** 파일 크기(byte). 폴더는 생략. */
  size?: number;
}

export interface FsListInput {
  /** 분석 대상 루트(절대경로) — 모든 접근의 상한. */
  root: string;
  /** 나열할 디렉터리(절대경로). 최초 호출은 root 와 동일. root 하위여야 함. */
  path: string;
}

export interface FsReadInput {
  root: string;
  /** 읽을 파일(절대경로). root 하위여야 함. */
  path: string;
}

/** 삭제/새폴더 등 단일 경로 변경. path 는 root 하위. */
export interface FsPathInput {
  root: string;
  path: string;
}

/** 이동(이름변경)/복사 — from·to 모두 root 하위. */
export interface FsMovePairInput {
  root: string;
  from: string;
  to: string;
}

/** 파일 텍스트 저장 — path 는 root 하위. */
export interface FsWriteInput {
  root: string;
  path: string;
  content: string;
}

/** 미리보기 결과 — 텍스트만 내용 반환, 바이너리/초대형은 렌더 안 함(spec FR-004·Edge). */
export type FsReadResult =
  | { kind: "text"; content: string }
  | { kind: "binary" }
  | { kind: "too-large"; size: number };

// ---------------------------------------------------------------------------
// Per-channel request/response map — composed with the 023 IpcRequestMap
// via declaration merging (launcher-contract.ts 와 동일 방식).
// ---------------------------------------------------------------------------

export interface FsBrowserIpcRequestMap {
  "fs:listDir": [FsListInput, FsEntry[]];
  "fs:readFile": [FsReadInput, FsReadResult];
  // 파일 작업 — 전부 root 하위 한정. 삭제는 휴지통(영구삭제 X).
  "fs:rename": [FsMovePairInput, { ok: true }];
  "fs:copy": [FsMovePairInput, { ok: true }];
  "fs:trash": [FsPathInput, { ok: true }];
  "fs:mkdir": [FsPathInput, { ok: true }];
  "fs:writeFile": [FsWriteInput, { ok: true }];
}

export type FsBrowserIpcChannel = keyof FsBrowserIpcRequestMap;

// ---------------------------------------------------------------------------
// Renderer surface (window.desktop.fs)
// ---------------------------------------------------------------------------

export interface FsBrowserDesktopBridge {
  fs: {
    listDir(input: FsListInput): Promise<IpcResult<FsEntry[]>>;
    readFile(input: FsReadInput): Promise<IpcResult<FsReadResult>>;
    rename(input: FsMovePairInput): Promise<IpcResult<{ ok: true }>>;
    copy(input: FsMovePairInput): Promise<IpcResult<{ ok: true }>>;
    trash(input: FsPathInput): Promise<IpcResult<{ ok: true }>>;
    mkdir(input: FsPathInput): Promise<IpcResult<{ ok: true }>>;
    writeFile(input: FsWriteInput): Promise<IpcResult<{ ok: true }>>;
  };
}

// ---------------------------------------------------------------------------
// Module augmentation — fold fs channels into the global IpcRequestMap +
// DesktopBridge so registerHandler 와 preload bridge 가 end-to-end 타입검사된다.
// ---------------------------------------------------------------------------

declare module "./ipc-contract" {
  interface IpcRequestMap extends FsBrowserIpcRequestMap {}
  interface DesktopBridge extends FsBrowserDesktopBridge {}
}
