/**
 * 런타임 감독 계약 — 앱이 수명을 책임지는 서비스와 그것이 받쳐 주는 기능 (spec 058).
 *
 * `contracts/runtime-status-ipc.md` · `data-model.md` §1~§3.
 *
 * ## 이 파일이 따로 있는 이유
 *
 * `ipc-contract.ts` 의 `RuntimeState` 는 **지우지 않는다** — `ClaudeCodeTerminal.vue` 와
 * `workspace.api.js` 가 `backendPort` 를 쓰고 있다. 여기 있는 것은 그 위에 **더해지는**
 * 것이고, 기존 `status` 는 이 값들에서 **파생**된다.
 *
 * ## 판정의 원칙 — 이 스펙 전체가 여기서 나왔다
 *
 * 2026-09-17 실측: `compose up --wait` 가 8/8 healthy 를 보고한 상태에서
 *
 *     자격증명 틀림   GET /healthz 200   POST /api/consulting-bpmn 502
 *     자격증명 맞음   GET /healthz 200   POST /api/consulting-bpmn 200
 *
 * **떴는지(health)와 일할 수 있는지(capability)는 다른 질문이다.** 그래서
 * `probeKind` 를 상태에 같이 싣는다 — 무엇으로 판정했는지 모르면 `ready` 를 믿을 수 없다.
 */

/** 프로브 결과. **넷을 뭉치지 않는다.** */
export type ProbeOutcome =
  /** 돌았고 조건을 맞췄다. */
  | "pass"
  /** 돌았는데 조건을 못 맞췄다. */
  | "fail"
  /** **프로브 자체가 못 돌았다** (도구 없음·연결 불가·설정 없음). "안 된다"가 아니라 "모른다". */
  | "error"
  /** 앞 단계가 안 돼서 재지 않았다. */
  | "skipped";

export type ProbeKind = "health" | "capability";

export interface ProbeResult {
  serviceId: ManagedServiceId;
  kind: ProbeKind;
  outcome: ProbeOutcome;
  /** 사람이 읽는 근거. **비밀정보 금지** — 길이나 지문으로도 남기지 않는다(FR-011). */
  detail: string;
  durationMs: number;
}

/**
 * 서비스 id. compose 의 `org.uengine.robo.component` 와 같은 값이고,
 * `architect` 만 호스트 프로세스다.
 *
 * `graph` 는 **엔진 이름이 아니라 역할 이름**이다. 설치본의 저장소는 Ontological 이고
 * 앱이 보는 것은 Neo4j **프로토콜**을 말하는 Bolt 게이트웨이다 — id 를 엔진에 묶으면
 * 엔진을 바꿀 때마다 계약이 깨진다(2026-09-17 에 실제로 바뀌었다).
 */
export type ManagedServiceId =
  | "graph"
  | "mindsdb"
  | "analyzer"
  | "catalog"
  | "fabric"
  | "parser"
  | "gateway"
  | "pdf2bpmn"
  | "architect";

export type ServiceOwner = "app" | "external";

export type ServiceState =
  | "pending"
  | "starting"
  | "ready"
  | "degraded"
  | "failed"
  | "stopped";

export interface ManagedService {
  id: ManagedServiceId;
  owner: ServiceOwner;
  displayName: string;
  state: ServiceState;
  /** 실패·저하일 때 필수. 비밀정보 금지. */
  stateReason: string | null;
  /** **무엇으로 판정했는지.** health 만 통과한 것은 `ready` 가 아니다. */
  probeKind: ProbeKind | null;
  lastProbeAt: string | null;
  lastProbeMs: number | null;
  restartCount: number;
  restartGaveUpAt: string | null;
  version: string | null;
  endpoint: string | null;
}

export type CapabilityId =
  | "design"
  | "document-ingestion"
  | "bpmn-generation"
  | "legacy-analysis"
  | "code-generation"
  | "collaboration";

export type CapabilityState = "available" | "unavailable" | "degraded";

export interface Capability {
  id: CapabilityId;
  displayName: string;
  requires: ManagedServiceId[];
  /** **파생값이다. 저장하지 않는다** — 두 곳에 같은 사실을 두면 어긋난다. */
  state: CapabilityState;
  /** 왜 못 쓰는가 + **사용자가 할 수 있는 일**. available 이면 null. */
  blockedReason: string | null;
}

/**
 * 기능이 어느 서비스에 걸려 있는가 — "analyzer 가 죽었다"를 "코드 분석 탭을 못 쓴다"로
 * 옮기는 표(FR-004). 이 표가 없으면 화면은 서비스 이름만 보여주고, 사용자는 자기가
 * 무엇을 못 하게 됐는지 모른다.
 */
export const CAPABILITY_REQUIREMENTS: ReadonlyArray<
  Pick<Capability, "id" | "displayName" | "requires">
> = [
  { id: "design", displayName: "설계", requires: ["graph", "architect"] },
  {
    id: "document-ingestion",
    displayName: "문서·리소스 업로드",
    requires: ["graph", "architect"],
  },
  {
    // 문서→BPMN 은 자체 호스팅 서비스가 낸다. 그게 죽으면 **다른 경로로 조용히
    // 성공해서는 안 된다**(FR-025) — 그래서 이 기능은 pdf2bpmn 에 명시적으로 걸린다.
    id: "bpmn-generation",
    displayName: "업무 흐름 BPMN 생성",
    requires: ["graph", "architect", "pdf2bpmn"],
  },
  {
    // **graph 분리가 깨졌으면 이 기능은 열리지 않는다**(§deriveCapabilities 의
    // `guard` 인자). 분석을 누른 뒤에 막으면 늦다 — 누르는 순간 대상 graph 가
    // 비워진다.
    id: "legacy-analysis",
    displayName: "레거시 코드 탐색",
    requires: ["graph", "analyzer", "catalog", "parser", "gateway"],
  },
  { id: "code-generation", displayName: "코드 생성", requires: ["graph", "architect"] },
  { id: "collaboration", displayName: "동시 편집", requires: ["graph", "architect"] },
];

/**
 * graph 분리 판정 — 분석이 설계를 지우는 구성을 **기동 시점에** 막는다(FR-008).
 *
 * 분석은 대상 graph 를 통째로 비우고 다시 쓴다. 두 graph 가 같으면 첫 분석에서 설계가
 * 사라진다. 실제로 한 번 날렸다.
 *
 * ## 무엇을 근거로 "분리됐다"고 하는가
 *
 * **빈 graph 로는 아무것도 증명하지 못한다.** 데이터가 없으면 지워져도 티가 안 나고,
 * 두 이름이 같은 저장소를 가리켜도 양쪽 조회가 0 건으로 똑같이 나온다.
 *
 * 그래서 근거를 값으로 남긴다.
 *
 * ```
 * "content"  양쪽에서 **서로 다른 내용**이 나왔다. 실제로 갈려 있다는 증거다
 * "names"    이름이 다르고 양쪽 조회가 돌았다. 다만 내용으로는 확인 못 했다
 *            (갓 설치한 상태가 정상적으로 여기다 — 막지 않는다)
 * null       판정하지 못했다
 * ```
 *
 * `separated: true` + `evidence: "names"` 를 "검증했다"로 읽지 않는다.
 */
export interface GraphGuard {
  designGraph: string | null;
  analysisGraph: string | null;
  /** 둘이 다르고 둘 다 조회되는가. `false` 면 분석 기능을 잠근다. */
  separated: boolean;
  /** 무엇으로 그렇게 판정했는가. **"names" 를 증명으로 읽지 않는다.** */
  evidence: "content" | "names" | null;
  reason: string | null;
}

export interface RuntimeStatusPayload {
  services: ManagedService[];
  capabilities: Capability[];
  graphGuard: GraphGuard | null;
  /** 화면이 **무엇이 바뀌었는지** 알아야 알림을 한 번만 띄운다. */
  changedServiceIds: ManagedServiceId[];
}

export const RUNTIME_CHANNELS = {
  onStatus: "runtime:onStatus",
  retryService: "runtime:retryService",
  stopEngine: "runtime:stopEngine",
  openDiagnostics: "runtime:openDiagnostics",
} as const;

// ---------------------------------------------------------------------------
// 파생 — 저장하지 않는다
// ---------------------------------------------------------------------------

/**
 * 서비스 상태 → 기능 상태.
 *
 * ```
 * requires 가 전부 ready            → available
 * 하나라도 failed/stopped           → unavailable
 * 하나라도 degraded (failed 없음)   → degraded
 * ```
 *
 * `pending`·`starting` 은 아직 결론이 아니므로 `unavailable` 로 둔다 — **화면이 그
 * 기능을 열어서는 안 된다.** 다만 이유는 "기동 중"이라고 말한다. "실패"와 "아직"을
 * 같은 문구로 보여주면 사용자가 잘못된 조치를 한다.
 */
/** graph 분리가 깨지면 못 쓰는 기능들. 분석은 대상 graph 를 비우고 다시 쓴다. */
export const GUARD_DEPENDENT_CAPABILITIES: readonly CapabilityId[] = ["legacy-analysis"];

export function deriveCapabilities(
  services: ManagedService[],
  guard?: GraphGuard | null,
): Capability[] {
  const byId = new Map(services.map((service) => [service.id, service]));
  return CAPABILITY_REQUIREMENTS.map((requirement) => {
    const needed = requirement.requires.map((id) => byId.get(id)).filter(Boolean) as ManagedService[];
    const missing = requirement.requires.filter((id) => !byId.has(id));
    const broken = needed.filter((s) => s.state === "failed" || s.state === "stopped");
    const waiting = needed.filter((s) => s.state === "pending" || s.state === "starting");
    const degraded = needed.filter((s) => s.state === "degraded");

    let state: CapabilityState = "available";
    let blockedReason: string | null = null;

    if (missing.length > 0) {
      // 표에 있는 서비스가 상태 목록에 아예 없다 — 재지 못한 것이다. 통과로 치지 않는다.
      state = "unavailable";
      blockedReason = `상태를 확인하지 못한 서비스가 있습니다: ${missing.join(", ")}`;
    } else if (broken.length > 0) {
      state = "unavailable";
      blockedReason = `${describe(broken)} 이(가) 준비되지 않았습니다. 런타임 상태에서 다시 시도할 수 있습니다.`;
    } else if (waiting.length > 0) {
      state = "unavailable";
      blockedReason = `${describe(waiting)} 이(가) 기동 중입니다. 잠시 뒤 다시 시도하세요.`;
    } else if (degraded.length > 0) {
      state = "degraded";
      blockedReason = `${describe(degraded)} 이(가) 떴지만 일할 수 없는 상태입니다. 설정을 확인하세요.`;
    }

    // **분리 판정은 서비스 상태와 독립이다.** 전부 ready 여도 두 graph 가 같으면
    // 이 기능을 열면 안 된다 — 여는 순간 설계가 지워진다.
    if (guard && guard.separated === false && GUARD_DEPENDENT_CAPABILITIES.includes(requirement.id)) {
      state = "unavailable";
      blockedReason =
        `설계 graph 와 분석 graph 가 분리되지 않았습니다. ${guard.reason ?? ""} ` +
        "이대로 분석을 시작하면 설계 데이터가 지워집니다. 설정을 먼저 고쳐 주세요.";
    }

    return { ...requirement, requires: [...requirement.requires], state, blockedReason };
  });
}

function describe(services: ManagedService[]): string {
  return services.map((service) => service.displayName).join(", ");
}
