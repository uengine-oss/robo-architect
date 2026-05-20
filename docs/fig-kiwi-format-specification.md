# Fig-Kiwi 바이너리 클립보드 포맷 상세 명세서

> Figma 데스크톱/웹 앱이 클립보드 복사·붙여넣기에 사용하는 내부 바이너리 포맷.
> robo-architect 프로젝트에서는 이 포맷을 읽고 쓰는 양방향 구현을 통해
> 와이어프레임 ↔ Figma 간 데이터 교환을 수행한다.

---

## 목차

1. [전체 아키텍처](#1-전체-아키텍처)
2. [Layer 1: HTML 클립보드 래퍼](#2-layer-1-html-클립보드-래퍼)
3. [Layer 2: Base64 인코딩](#3-layer-2-base64-인코딩)
4. [Layer 3: fig-kiwi 아카이브 (바이너리)](#4-layer-3-fig-kiwi-아카이브-바이너리)
5. [Layer 4: 압축 (Deflate / Zstd)](#5-layer-4-압축-deflate--zstd)
6. [Layer 5: Kiwi Schema 직렬화](#6-layer-5-kiwi-schema-직렬화)
7. [Layer 6: 메시지 페이로드 구조](#7-layer-6-메시지-페이로드-구조)
8. [Layer 7: NodeChange 상세 구조](#8-layer-7-nodechange-상세-구조)
9. [Layer 8: 메타데이터 (figmeta)](#9-layer-8-메타데이터-figmeta)
10. [데이터 타입 정의](#10-데이터-타입-정의)
11. [인코딩 파이프라인 (쓰기)](#11-인코딩-파이프라인-쓰기)
12. [디코딩 파이프라인 (읽기)](#12-디코딩-파이프라인-읽기)
13. [스키마 부트스트랩 메커니즘](#13-스키마-부트스트랩-메커니즘)
14. [WireframeElement 중간 표현](#14-wireframeelement-중간-표현)
15. [HTML → WireframeElement 변환 규칙](#15-html--wireframeelement-변환-규칙)
16. [WireframeElement → Figma NodeChange 변환 규칙](#16-wireframeelement--figma-nodechange-변환-규칙)
17. [GUID 생성 전략](#17-guid-생성-전략)
18. [색상 변환 규칙](#18-색상-변환-규칙)
19. [외부 의존성](#19-외부-의존성)
20. [제한사항 및 알려진 이슈](#20-제한사항-및-알려진-이슈)

---

## 1. 전체 아키텍처

fig-kiwi 포맷은 **7개 레이어**로 구성된 중첩 포맷이다:

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: HTML 클립보드 래퍼                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Layer 2: Base64 인코딩                                 │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Layer 3: fig-kiwi 아카이브 (바이너리 컨테이너)    │  │  │
│  │  │  ┌────────────────────────────────────────────┐  │  │  │
│  │  │  │  Layer 4: Deflate/Zstd 압축                 │  │  │  │
│  │  │  │  ┌──────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  Layer 5: Kiwi Schema 직렬화          │  │  │  │  │
│  │  │  │  │  ┌────────────────────────────────┐  │  │  │  │  │
│  │  │  │  │  │  Layer 6: 메시지 페이로드        │  │  │  │  │  │
│  │  │  │  │  │  ┌──────────────────────────┐  │  │  │  │  │  │
│  │  │  │  │  │  │  Layer 7: NodeChange[]    │  │  │  │  │  │  │
│  │  │  │  │  │  └──────────────────────────┘  │  │  │  │  │  │
│  │  │  │  │  └────────────────────────────────┘  │  │  │  │  │
│  │  │  │  └──────────────────────────────────────┘  │  │  │  │
│  │  │  └────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Layer 1: HTML 클립보드 래퍼

브라우저 Clipboard API를 통해 `text/html` MIME 타입으로 전달되는 최외곽 레이어.

### 구조

```html
<meta charset="utf-8" />
<meta charset="utf-8" />
<span
  data-metadata="<!--(figmeta)BASE64_ENCODED_META(/figmeta)-->"
></span>
<span
  data-buffer="<!--(figma)BASE64_ENCODED_ARCHIVE(/figma)-->"
></span>
<span style="white-space: pre-wrap"></span>
```

### 구성 요소

| 요소 | 역할 |
|------|------|
| `<meta charset="utf-8" />` × 2 | 문자 인코딩 선언 (중복은 Figma 원본 동작 유지) |
| `<span data-metadata="...">` | figmeta: JSON 메타데이터 (Base64) |
| `<span data-buffer="...">` | figma: fig-kiwi 바이너리 아카이브 (Base64) |
| `<span style="white-space: pre-wrap">` | Figma 호환성용 빈 span |

### 데이터 임베딩 형식

Base64 데이터는 HTML 주석 마커로 감싸진다:

```
<!--(figmeta)eyJmaWxlS2V5Ijoi...(/figmeta)-->
<!--(figma)ZmlnLWtpd2kP...(/figma)-->
```

- 시작 마커: `<!--(태그명)`
- 종료 마커: `(/태그명)-->`

### HTML 파싱 전략 (3단계 폴백)

시스템은 다양한 클립보드 구현에 대응하기 위해 3단계 파싱을 수행한다:

```
전략 1: 직접 문자열 검색
  html.indexOf('<!--(figmeta)') / html.indexOf('<!--(figma)')

전략 2: DOM 파싱
  DOMParser → querySelector('span[data-metadata]') / querySelector('span[data-buffer]')
  → extractBase64(attribute, tag)

전략 3: 정규식 폴백
  html.match(/data-metadata="([^"]*)"/)
  html.match(/data-buffer="([^"]*)"/)
```

---

## 3. Layer 2: Base64 인코딩

### figmeta (메타데이터)

```
원본 JSON 문자열 → btoa() → Base64 문자열
```

```javascript
// 인코딩
const metaB64 = btoa(JSON.stringify(meta))

// 디코딩
const meta = JSON.parse(atob(metaB64))
```

### figma (바이너리 아카이브)

```
Uint8Array 바이너리 → 바이트별 String.fromCharCode() → btoa() → Base64 문자열
```

```javascript
// 인코딩
function uint8ToBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

// 디코딩
const figma = Uint8Array.from(atob(figB64), c => c.charCodeAt(0))
```

> **참고**: `btoa()`/`atob()`는 Latin-1 범위(0x00-0xFF) 문자만 처리하므로
> 바이너리 데이터를 바이트 단위로 변환해야 한다.

---

## 4. Layer 3: fig-kiwi 아카이브 (바이너리)

### 바이너리 레이아웃

```
┌────────────────────────────────────────────────────────────────┐
│ Offset  │ Size    │ Type          │ 설명                       │
├─────────┼─────────┼───────────────┼────────────────────────────┤
│ 0x00    │ 8 bytes │ ASCII string  │ 매직 바이트: "fig-kiwi"    │
│ 0x08    │ 4 bytes │ uint32 LE     │ 버전 번호 (현재: 15)       │
│ 0x0C    │ 4 bytes │ uint32 LE     │ File 1 크기 (N1 바이트)    │
│ 0x10    │ N1      │ byte[]        │ File 1: 압축된 Kiwi Schema │
│ 0x10+N1 │ 4 bytes │ uint32 LE     │ File 2 크기 (N2 바이트)    │
│ 0x14+N1 │ N2      │ byte[]        │ File 2: 압축된 메시지 데이터│
└─────────┴─────────┴───────────────┴────────────────────────────┘
```

### 상세 필드 설명

#### 매직 바이트 (8 bytes)
```
66 69 67 2D 6B 69 77 69
 f  i  g  -  k  i  w  i
```
- ASCII 문자열 `"fig-kiwi"`
- 아카이브 식별자
- 이 값이 일치하지 않으면 파싱 실패

#### 버전 (4 bytes, Little-Endian uint32)
```
0F 00 00 00  →  15 (10진수)
```
- 현재 구현 기준: **버전 15**
- Figma 업데이트에 따라 증가할 수 있음
- 쓰기 시 항상 `FIG_KIWI_VERSION = 15` 사용

#### 파일 엔트리 (반복, 현재 2개)

각 파일 엔트리는:
```
[4 bytes: 파일 크기 (uint32 LE)] [N bytes: 파일 데이터]
```

| 인덱스 | 내용 | 압축 후 용도 |
|--------|------|-------------|
| File 0 | Kiwi Schema 정의 (바이너리) | 메시지 구조 정의 |
| File 1 | 메시지 데이터 (바이너리) | 실제 디자인 노드 데이터 |

### 아카이브 빌드 코드

```typescript
function buildArchive(files: Uint8Array[]): Uint8Array {
  const headerSize = 8 /* "fig-kiwi" */ + 4 /* version */
  const totalSize = files.reduce((s, f) => s + 4 + f.byteLength, headerSize)
  const buf = new Uint8Array(totalSize)
  const view = new DataView(buf.buffer)

  // 매직 바이트 기록
  let offset = new TextEncoder().encodeInto('fig-kiwi', buf).written!

  // 버전 기록 (Little-Endian)
  view.setUint32(offset, 15, true)
  offset += 4

  // 각 파일 기록
  for (const file of files) {
    view.setUint32(offset, file.byteLength, true)  // 크기
    offset += 4
    buf.set(file, offset)                           // 데이터
    offset += file.byteLength
  }

  return buf
}
```

### 헥스 덤프 예시

```
00000000  66 69 67 2D 6B 69 77 69  0F 00 00 00 A3 02 00 00  |fig-kiwi........|
00000010  78 9C ED 56 4D 6F DB 30  ...                       |x..VM.0. (schema)|
          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
          │                        │
          │  File 0 (Schema)       │
          │  크기: 0x000002A3      │
          │  = 675 bytes           │
          └────────────────────────┘

000002B7  8B 05 00 00 78 9C ED 5A  ...                       |(message data)    |
          ~~~~~~~~~~~~~~~~~~~~~~~~~~~
          │
          │  File 1 (Message)
          │  크기: 0x0000058B
          │  = 1419 bytes
          └──────────────────
```

---

## 5. Layer 4: 압축 (Deflate / Zstd)

아카이브 내부의 각 파일은 압축되어 있다.

### 압축 알고리즘 자동 감지

```typescript
function isZstd(buf: Uint8Array): boolean {
  return buf.length >= 4
    && buf[0] === 0x28   // '('
    && buf[1] === 0xB5   // 'µ'
    && buf[2] === 0x2F   // '/'
    && buf[3] === 0xFD   // 'ý'
}
```

| 매직 바이트 | 알고리즘 | 라이브러리 | 방향 |
|-------------|----------|-----------|------|
| `28 B5 2F FD` | Zstandard (zstd) | `fzstd` | 읽기 전용 |
| 기타 | Deflate Raw | `pako` | 읽기/쓰기 |

### 읽기 시 (디코딩)

```typescript
function decompressAuto(buf: Uint8Array): Uint8Array {
  if (isZstd(buf)) {
    return zstdDecompress(buf)   // fzstd 라이브러리
  }
  return inflateRaw(buf)         // pako 라이브러리
}
```

### 쓰기 시 (인코딩)

```typescript
// 항상 Deflate Raw 사용 (pako)
const schemaCompressed = deflateRaw(schemaBin)
const dataCompressed = deflateRaw(dataBin)
```

> **참고**: 쓰기 시에는 항상 **Deflate Raw**를 사용한다.
> Figma는 읽기 시 두 알고리즘 모두 지원하므로 호환성 문제 없음.
> Figma 자체는 최근 버전에서 zstd로 쓰기 때문에, 읽기 시에는 zstd 감지가 필요하다.

---

## 6. Layer 5: Kiwi Schema 직렬화

[Kiwi](https://github.com/nicbarker/kiwi-schema)는 Figma가 사용하는 자체 직렬화 포맷이다.
Protocol Buffers와 유사하지만, Figma에 특화된 메시지 구조를 가진다.

### Schema (File 0)

아카이브의 첫 번째 파일은 Kiwi Schema 정의(바이너리)로, 메시지 구조를 기술한다.

```typescript
// 디코딩
const schemaBuf = decompressAuto(schemaCompressed)
const schema = decodeBinarySchema(new ByteBuffer(schemaBuf))

// 인코딩
const schemaBin = encodeBinarySchema(schema)
```

Schema 객체는 Figma의 내부 메시지 구조를 정의하며, 다음을 포함한다:
- 메시지 타입 정의 (enum, struct, message)
- 필드 이름과 타입 매핑
- 중첩 구조 정의

### Message (File 1)

두 번째 파일은 Schema에 정의된 구조에 따라 인코딩된 실제 데이터이다.

```typescript
// 디코딩
const compiled = compileSchema(schema)
const dataBuf = decompressAuto(dataCompressed)
const message = compiled.decodeMessage(new ByteBuffer(dataBuf))

// 인코딩
const compiled = compileSchema(schema)
const dataBin = compiled.encodeMessage(message)
```

### Schema 캐싱

Figma의 Kiwi Schema는 비공개이므로, 런타임에 Figma 클립보드에서 캡처해야 한다:

```typescript
const SCHEMA_KEY = 'figma-schema-cache'

function getCachedSchema(): any | null {
  const raw = localStorage.getItem(SCHEMA_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

function cacheSchema(schema: any) {
  localStorage.setItem(SCHEMA_KEY, JSON.stringify(schema))
}
```

---

## 7. Layer 6: 메시지 페이로드 구조

Kiwi Schema로 인코딩/디코딩되는 최상위 메시지 구조.

### 전체 구조

```typescript
{
  type: 'NODE_CHANGES',         // 메시지 타입 (항상 'NODE_CHANGES')
  sessionID: 0,                 // 세션 ID (클립보드 붙여넣기 시 0)
  ackID: 0,                     // ACK ID (클립보드 붙여넣기 시 0)
  pasteID: number,              // 랜덤 양의 정수 (0 ~ 2^31-1)
  pasteFileKey: string,         // 랜덤 22자 영숫자 문자열
  pastePageId: GUID,            // 붙여넣기 대상 페이지 (항상 0:1)
  isCut: boolean,               // 잘라내기 여부 (항상 false)
  pasteEditorType: 'DESIGN',    // 에디터 타입 (항상 'DESIGN')
  nodeChanges: NodeChange[],    // 디자인 노드 배열 ★ 핵심 데이터
  blobs: [],                    // 바이너리 블롭 (이미지 등, 현재 미사용)
}
```

### 필드 상세

| 필드 | 타입 | 설명 | 생성 방식 |
|------|------|------|----------|
| `type` | string | 항상 `'NODE_CHANGES'` | 상수 |
| `sessionID` | number | 세션 식별자 | `0` |
| `ackID` | number | 응답 ID | `0` |
| `pasteID` | number | 붙여넣기 고유 ID | `Math.floor(Math.random() * 2147483647)` |
| `pasteFileKey` | string | 파일 키 (22자) | 랜덤 영숫자 생성 |
| `pastePageId` | GUID | 대상 페이지 | `{ sessionID: 0, localID: 1 }` |
| `isCut` | boolean | 잘라내기 여부 | `false` |
| `pasteEditorType` | string | 에디터 타입 | `'DESIGN'` |
| `nodeChanges` | NodeChange[] | 노드 변경 목록 | 디자인 노드 변환 결과 |
| `blobs` | any[] | 바이너리 데이터 | `[]` (빈 배열) |

### pasteFileKey 생성

```typescript
function generateFileKey(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let key = ''
  for (let i = 0; i < 22; i++) {
    key += chars[Math.floor(Math.random() * chars.length)]
  }
  return key
}
// 예: "aB3kL9mNpQrStUvWxYz12"
```

### nodeChanges 배열 구성 순서

```typescript
nodeChanges: [
  makeDocumentNode(),      // [0] 루트 문서 노드 (항상 첫 번째)
  makeCanvasNode(),        // [1] 메인 페이지 (Page 1)
  ...designNodes,          // [2..N] 사용자 디자인 노드들
  makeInternalCanvas(),    // [N+1] Figma 내부 캔버스 (항상 마지막)
]
```

---

## 8. Layer 7: NodeChange 상세 구조

### NodeChange 인터페이스 전체 정의

```typescript
interface NodeChange {
  // ── 식별 ──
  guid: GUID                           // 노드 고유 식별자
  phase?: string                       // 'CREATED' | 기타

  // ── 계층 구조 ──
  parentIndex?: {
    guid: GUID                         // 부모 노드 GUID
    position: string                   // 정렬 위치 문자열
  }

  // ── 기본 속성 ──
  type: string                         // 노드 타입 (아래 참조)
  name?: string                        // 레이어 이름
  visible?: boolean                    // 가시성
  opacity?: number                     // 투명도 (0.0 ~ 1.0)

  // ── 크기 & 위치 ──
  size?: Vector                        // { x: width, y: height }
  transform?: Matrix                   // 2D 어핀 변환 행렬

  // ── 채우기 & 테두리 ──
  fillPaints?: Paint[]                 // 채우기 페인트 배열
  strokePaints?: Paint[]               // 테두리 페인트 배열
  strokeWeight?: number                // 테두리 두께
  strokeAlign?: string                 // 'CENTER' | 'INSIDE' | 'OUTSIDE'
  strokeJoin?: string                  // 'MITER' | 'BEVEL' | 'ROUND'
  cornerRadius?: number                // 모서리 반경

  // ── 블렌드 ──
  blendMode?: string                   // 'NORMAL' | 'MULTIPLY' | ...

  // ── Auto Layout (Flex) ──
  stackMode?: string                   // 'VERTICAL' | 'HORIZONTAL'
  stackSpacing?: number                // 자식 간 간격
  stackHorizontalPadding?: number      // 좌측 패딩
  stackVerticalPadding?: number        // 상단 패딩
  stackPaddingRight?: number           // 우측 패딩
  stackPaddingBottom?: number          // 하단 패딩
  stackPrimarySizing?: string          // 'AUTO' | 'FIXED'
  stackCounterSizing?: string          // 'AUTO' | 'FIXED'
  stackCounterAlignItems?: string      // 'MIN' | 'CENTER' | 'MAX'
  stackChildAlignSelf?: string         // 'AUTO' | 'STRETCH'
  stackChildPrimaryGrow?: number       // flex-grow

  // ── 텍스트 속성 ──
  textData?: TextData                  // 텍스트 내용 데이터
  fontSize?: number                    // 폰트 크기 (px)
  fontName?: FontName                  // 폰트 패밀리/스타일
  textAlignHorizontal?: string         // 'LEFT' | 'CENTER' | 'RIGHT' | 'JUSTIFIED'
  textAlignVertical?: string           // 'TOP' | 'CENTER' | 'BOTTOM'
  textAutoResize?: string              // 'NONE' | 'HEIGHT' | 'WIDTH_AND_HEIGHT'
  autoRename?: boolean                 // 텍스트 변경 시 레이어 이름 자동 변경
  textTracking?: number                // 자간
  lineHeight?: LineHeight              // 행간
  letterSpacing?: LetterSpacing        // 글자 간격
  fontVariantCommonLigatures?: boolean // 합자 사용
  fontVariantContextualLigatures?: boolean
  textUserLayoutVersion?: number       // 텍스트 레이아웃 버전
  textBidiVersion?: number             // 양방향 텍스트 버전

  // ── 프레임 속성 ──
  frameMaskDisabled?: boolean          // 마스크 비활성화

  // ── 캔버스 속성 ──
  backgroundOpacity?: number           // 배경 투명도
  backgroundEnabled?: boolean          // 배경 활성화
  internalOnly?: boolean               // 내부 전용 캔버스

  // ── 제약 조건 ──
  horizontalConstraint?: string        // 'MIN' | 'CENTER' | 'MAX' | 'STRETCH' | 'SCALE'
  verticalConstraint?: string          // 'MIN' | 'CENTER' | 'MAX' | 'STRETCH' | 'SCALE'

  // ── 확장 필드 ──
  [key: string]: any                   // Kiwi Schema에 정의된 기타 필드
}
```

### 노드 타입

| type | 설명 | 용도 |
|------|------|------|
| `DOCUMENT` | 문서 루트 | 최상위 노드, 항상 1개 |
| `CANVAS` | 페이지/캔버스 | 페이지 컨테이너 |
| `FRAME` | 프레임 | 컨테이너, 카드, 네비바, 버튼 외곽, 인풋 외곽 등 |
| `RECTANGLE` | 사각형 | 단순 도형, 테이블 배경 등 |
| `TEXT` | 텍스트 | 모든 텍스트 요소 |
| `ELLIPSE` | 타원/원 | 원형 도형 |

### 시스템 노드 (항상 존재)

#### Document 노드
```typescript
{
  guid: { sessionID: 0, localID: 0 },   // 항상 0:0
  phase: 'CREATED',
  type: 'DOCUMENT',
  name: 'Document',
  visible: true,
  opacity: 1,
  transform: { m00:1, m01:0, m02:0, m10:0, m11:1, m12:0 },
}
```

#### Canvas 노드 (메인 페이지)
```typescript
{
  guid: { sessionID: 0, localID: 1 },   // 항상 0:1
  phase: 'CREATED',
  parentIndex: {
    guid: { sessionID: 0, localID: 0 }, // Document가 부모
    position: '!'                        // 첫 번째 자식
  },
  type: 'CANVAS',
  name: 'Page 1',
  visible: true,
  opacity: 1,
  transform: { m00:1, m01:0, m02:0, m10:0, m11:1, m12:0 },
  backgroundOpacity: 1,
  backgroundEnabled: true,
}
```

#### Internal Canvas 노드
```typescript
{
  guid: { sessionID: 20002313, localID: 2 },  // 특수 ID
  phase: 'CREATED',
  parentIndex: {
    guid: { sessionID: 0, localID: 0 },       // Document가 부모
    position: '"'                               // 두 번째 자식
  },
  type: 'CANVAS',
  name: 'Internal Only Canvas',
  visible: false,                               // 보이지 않음
  opacity: 1,
  transform: { m00:1, m01:0, m02:0, m10:0, m11:1, m12:0 },
  backgroundOpacity: 1,
  backgroundEnabled: false,
  internalOnly: true,                            // 내부 전용 플래그
}
```

---

## 9. Layer 8: 메타데이터 (figmeta)

HTML 클립보드의 `data-metadata` 속성에 Base64로 인코딩된 JSON.

### 구조

```json
{
  "fileKey": "aB3kL9mNpQrStUvWxYz12",
  "pasteID": 1234567890,
  "dataType": "scene"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `fileKey` | string (22자) | Figma 파일 식별자 (랜덤 생성) |
| `pasteID` | number | 붙여넣기 고유 ID (메시지의 pasteID와 동일) |
| `dataType` | string | 데이터 유형 (항상 `"scene"`) |

---

## 10. 데이터 타입 정의

### GUID

```typescript
interface GUID {
  sessionID: number    // 세션 식별자 (0=시스템, 312=생성된 노드)
  localID: number      // 세션 내 로컬 고유 ID
}
```

### Vector

```typescript
interface Vector {
  x: number    // 너비 (size) 또는 X좌표
  y: number    // 높이 (size) 또는 Y좌표
}
```

### Matrix (2D 어핀 변환)

```typescript
interface Matrix {
  m00: number    // scaleX     (기본: 1)
  m01: number    // skewX      (기본: 0)
  m02: number    // translateX (= x 좌표)
  m10: number    // skewY      (기본: 0)
  m11: number    // scaleY     (기본: 1)
  m12: number    // translateY (= y 좌표)
}
```

변환 행렬 시각화:
```
┌ m00  m01  m02 ┐     ┌ scaleX  skewX   x ┐
│ m10  m11  m12 │  =  │ skewY   scaleY  y │
└  0    0    1  ┘     └  0       0      1 ┘
```

단순 이동(translation)의 경우:
```typescript
makeTransform(x, y) → { m00:1, m01:0, m02:x, m10:0, m11:1, m12:y }
```

### Color

```typescript
interface Color {
  r: number    // Red   (0.0 ~ 1.0)
  g: number    // Green (0.0 ~ 1.0)
  b: number    // Blue  (0.0 ~ 1.0)
  a: number    // Alpha (0.0 ~ 1.0)
}
```

> **중요**: Figma는 0~1 범위의 부동소수점을 사용한다 (0~255가 아님).

### Paint

```typescript
interface Paint {
  type: string       // 'SOLID' | 'GRADIENT_LINEAR' | ...
  color?: Color      // SOLID 타입 시 색상
  opacity?: number   // 0.0 ~ 1.0
  visible?: boolean  // 페인트 가시성
  blendMode?: string // 'NORMAL' | 'MULTIPLY' | ...
}
```

### TextData

```typescript
interface TextData {
  characters: string    // 텍스트 내용
  lines: TextLine[]     // 줄 정보 배열
}

interface TextLine {
  lineType: string              // 'PLAIN' | 'ORDERED_LIST' | 'UNORDERED_LIST'
  styleId: number               // 스타일 참조 (기본: 0)
  indentationLevel: number      // 들여쓰기 레벨
  sourceDirectionality: string  // 'AUTO' | 'LTR' | 'RTL'
  listStartOffset: number       // 리스트 시작 번호
  isFirstLineOfList: boolean    // 리스트 첫 줄 여부
}
```

### FontName

```typescript
interface FontName {
  family: string       // 폰트 패밀리 (예: 'Inter')
  style: string        // 폰트 스타일 (예: 'Regular', 'Bold')
  postscript: string   // PostScript 이름 (보통 빈 문자열)
}
```

### LineHeight / LetterSpacing

```typescript
interface LineHeight {
  value: number        // 값 (0 = 자동)
  units: string        // 'RAW' | 'PIXELS' | 'PERCENT'
}

interface LetterSpacing {
  value: number        // 값
  units: string        // 'PIXELS' | 'PERCENT'
}
```

---

## 11. 인코딩 파이프라인 (쓰기)

와이어프레임 HTML → Figma 클립보드로 변환하는 전체 흐름.

```
                    ┌─────────────────┐
                    │ HTML 와이어프레임 │
                    │ (wf-* 클래스)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ DOMParser로 파싱  │  parseHtmlWireframe()
                    │ wf-* 클래스 감지  │
                    │ 40+ 변환기 적용   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ WireframeElement[] │  중간 표현 (IR)
                    │ {type, x, y,      │
                    │  width, height,    │
                    │  children, ...}    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ convertElement()  │  WireframeElement → NodeChange
                    │ 재귀적 변환       │  타입별 매핑
                    │ 색상 변환         │  hexToColor()
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ NodeChange[]     │  Figma 호환 노드 배열
                    │ (디자인 노드)     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐  ┌──▼──────────┐  ┌▼──────────────┐
     │ Document 노드   │  │ Canvas 노드  │  │ Internal 노드  │
     │ (0:0)           │  │ (0:1)        │  │ (20002313:2)   │
     └────────┬───────┘  └──┬──────────┘  └┬──────────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │ buildPasteMessage│  메시지 조립
                    │ + buildMeta()   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ FigmaClipboardData │
                    │ { meta, schema,    │
                    │   message }        │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
  ┌─────▼──────┐    ┌───────▼───────┐    ┌───────▼───────┐
  │ Schema →    │    │ Message →      │    │ Meta →        │
  │ encodeBinary│    │ encodeMessage  │    │ JSON.stringify│
  │ Schema()    │    │ (compiled)     │    │ → btoa()      │
  │ → deflateRaw│    │ → deflateRaw() │    │               │
  └─────┬──────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────┬───────────┘                    │
                 │                                │
        ┌────────▼────────┐                       │
        │ buildArchive()  │                       │
        │ [schema, data]  │                       │
        │ → fig-kiwi bin  │                       │
        └────────┬────────┘                       │
                 │                                │
        ┌────────▼────────┐                       │
        │ uint8ToBase64() │                       │
        └────────┬────────┘                       │
                 │                                │
        ┌────────▼────────────────────────────────▼──┐
        │ composeHTMLClipboard(meta, archive)         │
        │ → HTML 문자열 생성                           │
        └────────┬───────────────────────────────────┘
                 │
        ┌────────▼────────┐
        │ copyToClipboard │  navigator.clipboard.write()
        │ text/html +     │  ClipboardItem API
        │ text/plain      │
        └─────────────────┘
```

---

## 12. 디코딩 파이프라인 (읽기)

Figma 클립보드 → 내부 데이터 구조로 변환하는 전체 흐름.

```
        ┌─────────────────────────────┐
        │ 브라우저 paste 이벤트        │
        │ clipboardData.getData(       │
        │   'text/html')               │
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────┐
        │ parseHTMLClipboard(html)    │
        │ 3단계 폴백 파싱:             │
        │  1. 직접 문자열 검색         │
        │  2. DOMParser               │
        │  3. 정규식                   │
        └────────────┬────────────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
   ┌───────▼──────┐    ┌──────▼──────┐
   │ metaB64      │    │ figB64      │
   │ → atob()     │    │ → Uint8Array │
   │ → JSON.parse │    │ .from(atob) │
   └───────┬──────┘    └──────┬──────┘
           │                   │
           │           ┌──────▼──────┐
           │           │ parseArchive│
           │           │ 매직 확인    │
           │           │ 버전 읽기    │
           │           │ 파일 추출    │
           │           └──────┬──────┘
           │                  │
           │         ┌───────┴───────┐
           │         │               │
           │   ┌─────▼─────┐  ┌─────▼─────┐
           │   │ File 0     │  │ File 1     │
           │   │ decompress │  │ decompress │
           │   │ Auto()     │  │ Auto()     │
           │   └─────┬─────┘  └─────┬─────┘
           │         │               │
           │   ┌─────▼─────┐  ┌─────▼─────┐
           │   │ decodeBin  │  │ compiled.  │
           │   │ arySchema()│  │ decode     │
           │   │ → schema   │  │ Message()  │
           │   │            │  │ → message  │
           │   └─────┬─────┘  └─────┬─────┘
           │         │               │
   ┌───────▼─────────▼───────────────▼───────┐
   │ FigmaClipboardData                       │
   │ { meta, schema, message }                │
   │                                          │
   │ message.nodeChanges[] ← 디자인 노드 배열  │
   └──────────────────────────────────────────┘
```

---

## 13. 스키마 부트스트랩 메커니즘

Figma의 Kiwi Schema는 비공개이므로, 시스템 최초 사용 시 사용자가 직접 캡처해야 한다.

### 부트스트랩 프로세스

```
┌────────────────────────────────────────────────────────────────┐
│ 1. 사용자가 "Export to Figma" 버튼 클릭                         │
│                                                                │
│ 2. getCachedSchema() 호출                                      │
│    └─ localStorage.getItem('figma-schema-cache')               │
│                                                                │
│ 3-A. 캐시 있음 → 바로 내보내기 진행                              │
│                                                                │
│ 3-B. 캐시 없음 → 모달 표시:                                     │
│    "Figma에서 아무 요소를 복사(Ctrl+C)한 후                       │
│     이 입력 필드에 붙여넣기(Ctrl+V)해주세요"                      │
│                                                                │
│ 4. 사용자가 Figma에서 요소 복사 → 모달에 붙여넣기                 │
│                                                                │
│ 5. onFigmaSchemaPaste() 실행:                                  │
│    ├─ readClipboardHTML(pastedHtml)                            │
│    ├─ schema 추출                                              │
│    ├─ cacheSchema(schema)                                      │
│    │  └─ localStorage.setItem('figma-schema-cache', JSON)     │
│    └─ 내보내기 자동 재시도                                       │
│                                                                │
│ 6. 이후 사용 시 캐시된 스키마 재사용 (브라우저 종료까지 유지)      │
└────────────────────────────────────────────────────────────────┘
```

> **주의**: Figma가 스키마를 변경하면 캐시를 갱신해야 할 수 있다.
> `localStorage.removeItem('figma-schema-cache')`로 수동 초기화 가능.

---

## 14. WireframeElement 중간 표현

HTML과 Figma NodeChange 사이의 추상화 레이어.

### 타입 정의

```typescript
type WireframeElementType =
  | 'frame'      // 일반 컨테이너
  | 'rectangle'  // 사각형 도형
  | 'text'       // 텍스트
  | 'ellipse'    // 타원/원
  | 'button'     // 버튼 (FRAME + TEXT로 변환)
  | 'input'      // 입력 필드 (FRAME + TEXT로 변환)
  | 'navbar'     // 네비게이션 바 → FRAME
  | 'card'       // 카드 → FRAME
  | 'sidebar'    // 사이드바 → FRAME

interface WireframeElement {
  id: string                                    // 고유 ID (예: 'imp-1')
  type: WireframeElementType                    // 요소 타입
  x: number                                     // X 좌표 (부모 기준)
  y: number                                     // Y 좌표 (부모 기준)
  width: number                                 // 너비 (px)
  height: number                                // 높이 (px)
  label?: string                                // 텍스트 라벨
  children?: WireframeElement[]                  // 자식 요소
  fillColor?: string                            // 채우기 색상 (#RRGGBB 또는 #RRGGBBAA)
  strokeColor?: string                          // 테두리 색상
  strokeWidth?: number                          // 테두리 두께
  cornerRadius?: number                         // 모서리 반경
  fontSize?: number                             // 폰트 크기
  textAlign?: 'LEFT' | 'CENTER' | 'RIGHT'       // 텍스트 정렬
  opacity?: number                              // 투명도 (0~1)
}
```

---

## 15. HTML → WireframeElement 변환 규칙

### CSS 클래스 기반 매핑 (우선순위순)

| CSS 클래스 | WireframeElement 타입 | 변환 함수 |
|-----------|----------------------|----------|
| `wf-appbar` | navbar | `convertAppbar()` |
| `wf-card` | card | `convertCard()` |
| `wf-table` (TABLE 태그) | frame | `convertTable()` |
| `wf-table__toolbar` | frame | `convertToolbar()` |
| `wf-pagination` | frame | `convertPagination()` |
| `wf-grid` | frame | `convertGrid()` |
| `wf-btn--primary` | button (#1890ff) | `convertButton()` |
| `wf-btn` | button (#f5f5f5) | `convertButton()` |
| `wf-input` | input | `convertInput()` |
| `wf-actions` | frame | `convertActions()` |
| `wf-chip` | button (pill형) | `convertChip()` |
| `wf-badge` | button (pill형) | `convertBadge()` |
| `wf-state` | frame | `convertState()` |
| `wf-empty` | frame | `convertEmpty()` |
| `wf-title`, `wf-card__title` | text | `convertText()` |
| `wf-subtitle` | text (12px, #8c8c8c) | `convertText()` |
| `wf-label` | text (12px) | `convertLabel()` |

### HTML 태그 기반 매핑 (CSS 클래스 미매치 시)

| HTML 태그 | 조건 | WireframeElement 타입 |
|-----------|------|----------------------|
| `INPUT[type=checkbox/radio]` | - | frame (16×16, 체크박스/라디오) |
| `INPUT`, `TEXTAREA`, `SELECT` | - | input |
| `BUTTON` | - | button |
| `TABLE` | - | frame (테이블) |
| `LABEL` | - | text |
| 컨테이너 태그 (DIV, SPAN 등) | 텍스트만 있음 | text |
| 컨테이너 태그 | display:flex | frame (flex row) |
| 컨테이너 태그 | 자식 있음 | frame (재귀) |

### 그리드 시스템

```
wf-grid 컨테이너 내부:
├─ wf-col-3  → 3/12 너비 (25%)
├─ wf-col-4  → 4/12 너비 (33.3%)
├─ wf-col-6  → 6/12 너비 (50%)
├─ wf-col-8  → 8/12 너비 (66.7%)
└─ wf-col-12 → 12/12 너비 (100%)

colWidth = (maxWidth - gap × 11) / 12 × colSpan + gap × (colSpan - 1)
gap = 10px
```

---

## 16. WireframeElement → Figma NodeChange 변환 규칙

### 타입별 매핑

| WireframeElement | Figma NodeChange | 특이사항 |
|------------------|-----------------|---------|
| `frame` | FRAME | 흰색 배경 |
| `navbar` | FRAME | 흰색 배경 |
| `card` | FRAME | 흰색 배경 |
| `sidebar` | FRAME | 흰색 배경 |
| `rectangle` | RECTANGLE | 회색 배경 (#d9d9d9) |
| `text` | TEXT | 검정 텍스트, Inter 16px |
| `ellipse` | ELLIPSE | 회색 배경 (#d9d9d9) |
| `button` | FRAME + TEXT (2노드) | 배경색 기반 텍스트 색상 자동 결정 |
| `input` | FRAME + TEXT (2노드) | 테두리 1px, 플레이스홀더 회색 |

### 버튼 텍스트 색상 자동 결정

```typescript
// YIQ 밝기 공식
const brightness = r * 0.299 + g * 0.587 + b * 0.114

if (brightness > 0.6) {
  textColor = { r: 0.12, g: 0.12, b: 0.12, a: 1 }  // 어두운 텍스트
} else {
  textColor = { r: 1, g: 1, b: 1, a: 1 }            // 흰 텍스트
}
```

### 기본 색상표

| 요소 | 속성 | 기본값 | Hex |
|------|------|--------|-----|
| Frame/Card/Navbar | fillColor | `{1, 1, 1, 1}` | #FFFFFF |
| Rectangle | fillColor | `{0.85, 0.85, 0.85, 1}` | #D9D9D9 |
| Ellipse | fillColor | `{0.85, 0.85, 0.85, 1}` | #D9D9D9 |
| Text | fillColor (=color) | `{0, 0, 0, 1}` | #000000 |
| Button | fillColor | `{0.23, 0.52, 0.96, 1}` | #3B85F5 |
| Input | fillColor | `{1, 1, 1, 1}` | #FFFFFF |
| Input | strokeColor | `{0.8, 0.8, 0.8, 1}` | #CCCCCC |
| Input placeholder | fillColor (=color) | `{0.6, 0.6, 0.6, 1}` | #999999 |

### 기본 폰트 설정

```typescript
{
  fontFamily: 'Inter',
  fontStyle: 'Regular',
  fontSize: 16,              // 텍스트 기본
  // fontSize: 14,           // 버튼/인풋 기본
  textAlignHorizontal: 'LEFT',
  textAlignVertical: 'TOP',
  textAutoResize: 'WIDTH_AND_HEIGHT',
  lineHeight: { value: 0, units: 'RAW' },     // 자동
  letterSpacing: { value: 0, units: 'PIXELS' },
}
```

---

## 17. GUID 생성 전략

### 시스템 노드 (고정 GUID)

| 노드 | sessionID | localID | 용도 |
|------|-----------|---------|------|
| Document | 0 | 0 | 루트 |
| Canvas (Page 1) | 0 | 1 | 메인 페이지 |
| Internal Canvas | 20002313 | 2 | 내부 전용 |

### 디자인 노드 (동적 GUID)

```typescript
const SESSION_ID = 312           // 모든 생성 노드의 sessionID
let localIdCounter = 100         // 시작값

function resetGuidCounter() {    // 내보내기 시작 시 초기화
  localIdCounter = 100
}

function makeGuid(): GUID {
  return {
    sessionID: SESSION_ID,       // 312
    localID: localIdCounter++    // 100, 101, 102, ...
  }
}
```

### 정렬 위치 (position)

Figma의 자식 정렬은 문자열 기반이다:

```typescript
function sortPosition(index: number): string {
  return String.fromCharCode(33 + index)
}
```

| index | position | ASCII |
|-------|----------|-------|
| 0 | `!` | 33 |
| 1 | `"` | 34 |
| 2 | `#` | 35 |
| 3 | `$` | 36 |
| ... | ... | ... |

---

## 18. 색상 변환 규칙

### Hex → Figma Color

```typescript
function hexToColor(hex: string, fallback: Color): Color {
  if (!hex) return fallback
  hex = hex.replace('#', '')
  if (hex.length === 6) hex += 'ff'  // 알파 채널 기본값: 완전 불투명
  return {
    r: parseInt(hex.slice(0, 2), 16) / 255,   // 0x00~0xFF → 0.0~1.0
    g: parseInt(hex.slice(2, 4), 16) / 255,
    b: parseInt(hex.slice(4, 6), 16) / 255,
    a: parseInt(hex.slice(6, 8), 16) / 255,
  }
}
```

### 변환 예시

| 입력 | r | g | b | a |
|------|---|---|---|---|
| `#FF0000` | 1.0 | 0.0 | 0.0 | 1.0 |
| `#1890ff` | 0.094 | 0.565 | 1.0 | 1.0 |
| `#00000080` | 0.0 | 0.0 | 0.0 | 0.502 |
| `#FFFFFF` | 1.0 | 1.0 | 1.0 | 1.0 |
| `undefined` | (fallback) | | | |

---

## 19. 외부 의존성

### npm 패키지

| 패키지 | 버전 | 역할 |
|--------|------|------|
| `kiwi-schema` | 0.5.0 | Kiwi Schema 인코딩/디코딩, 바이너리 스키마 처리 |
| `pako` | 2.x | Deflate Raw 압축/해제 (`deflateRaw`, `inflateRaw`) |
| `fzstd` | 0.1.1 | Zstandard 해제 전용 (`decompress`) |

### 사용 함수

```
kiwi-schema:
  ├─ compileSchema(schema)        → 컴파일된 코덱
  ├─ encodeBinarySchema(schema)   → Uint8Array (스키마 바이너리)
  ├─ decodeBinarySchema(buffer)   → schema 객체
  └─ ByteBuffer                   → 바이너리 버퍼 래퍼

pako:
  ├─ deflateRaw(data)             → Uint8Array (압축)
  └─ inflateRaw(data)             → Uint8Array (해제)

fzstd:
  └─ decompress(data)             → Uint8Array (zstd 해제)
```

### 브라우저 API

| API | 용도 |
|-----|------|
| `navigator.clipboard.write()` | 클립보드 쓰기 |
| `ClipboardItem` | 다중 MIME 타입 클립보드 아이템 |
| `DOMParser` | HTML 문자열 파싱 |
| `TextEncoder` | 문자열 → Uint8Array |
| `DataView` | 바이너리 데이터 읽기/쓰기 |
| `localStorage` | 스키마 캐시 저장 |
| `btoa()` / `atob()` | Base64 인코딩/디코딩 |

---

## 20. 제한사항 및 알려진 이슈

### 포맷 관련

1. **스키마 비호환성**: Figma가 Kiwi Schema를 업데이트하면 캐시된 스키마와 호환되지 않을 수 있음. `localStorage.removeItem('figma-schema-cache')`로 초기화 필요.

2. **버전 고정**: 아카이브 버전이 `15`로 하드코딩되어 있어, Figma가 버전을 올리면 수정 필요.

3. **쓰기 시 Deflate만 사용**: zstd 압축 쓰기는 미구현. Figma가 Deflate를 지원하므로 문제없지만, 파일 크기가 zstd 대비 클 수 있음.

### 변환 관련

4. **이미지 미지원**: `blobs` 배열이 항상 비어있어 이미지/비트맵 내보내기 불가.

5. **그라디언트 미지원**: Paint 타입이 `SOLID`만 구현. 그라디언트 색상은 무시됨.

6. **컴포넌트/인스턴스 미지원**: Figma의 Component, Instance 노드 타입 미구현.

7. **Auto Layout 제한**: 기본적인 VERTICAL/HORIZONTAL 레이아웃만 지원. `WRAP`, `SPACE_BETWEEN` 등 고급 옵션 미구현.

8. **폰트 제한**: `Inter Regular`만 사용. 사용자 시스템에 Inter 폰트가 없으면 Figma가 대체 폰트로 렌더링.

9. **sortPosition 범위**: ASCII 문자 기반이므로 자식 노드가 93개(33~126)를 초과하면 위치 충돌 가능.

---

## 소스 파일 참조

| 파일 | 주요 역할 |
|------|----------|
| `frontend/src/features/canvas/ui/figma/figkiwi.ts` | 바이너리 아카이브 인코딩/디코딩, 스키마 캐시 |
| `frontend/src/features/canvas/ui/figma/nodes.ts` | NodeChange 인터페이스, 노드 빌더 함수 |
| `frontend/src/features/canvas/ui/figma/types.ts` | WireframeElement 타입 정의 |
| `frontend/src/features/canvas/ui/figma/converter.ts` | WireframeElement → Figma 변환, 클립보드 복사 |
| `frontend/src/features/canvas/ui/figma/htmlParser.ts` | HTML → WireframeElement 파싱 (40+ 변환기) |
| `frontend/src/features/canvas/ui/figma/index.ts` | Public API 재수출 |
| `frontend/src/features/canvas/ui/InspectorPanel.vue` | UI 트리거 (exportToFigma, onFigmaSchemaPaste) |
