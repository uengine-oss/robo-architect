/**
 * 런타임 상태를 한 곳에서 모아 렌더러에 올린다 (spec 058 T034).
 *
 * ## 왜 따로 있나
 *
 * `index.ts` 의 `buildRuntimeState()` 는 하드코딩된 값을 돌려주고 있었다
 * (`boltPort: null`, `neo4jPid: null`, `updateState: "idle"`). 거기에 서비스 감독을
 * 끼워 넣으면 그 파일이 앱 기동·프로토콜·IPC·감독을 다 갖게 된다. 모으는 책임만
 * 여기로 뺀다.
 *
 * ## 이 파일이 지키는 것
 *
 * **파생값을 저장하지 않는다.** `capabilities` 와 하위 호환 `status` 는 `services` 와
 * `graphGuard` 에서 매번 계산한다. 두 곳에 같은 사실을 두면 어긋난다.
 *
 * **`graphGuard` 는 서비스 상태와 독립이다.** 전부 `ready` 여도 두 graph 가 같으면
 * 분석을 열면 안 된다 — 여는 순간 지워진다. 그래서 기능 파생에 가드를 같이 넘긴다.
 */

import {
  deriveCapabilities,
  type Capability,
  type GraphGuard,
  type LegacyDataNotice,
  type ManagedService,
  type ManagedServiceId,
  type ProbeKind,
  type ProbeResult,
} from "../shared/runtime-contract";
import { changedServiceIds, decideState, deriveLegacyStatus, type ServiceFacts } from "./supervisor";

const DISPLAY_NAMES: Record<ManagedServiceId, string> = {
  graph: "그래프 저장소",
  mindsdb: "데이터 연결(MindsDB)",
  analyzer: "코드 분석기",
  catalog: "데이터 카탈로그",
  fabric: "데이터 패브릭",
  parser: "코드 파서",
  gateway: "API 게이트웨이",
  pdf2bpmn: "문서→BPMN 생성기",
  architect: "Architect 백엔드",
};

/** `architect` 만 호스트 프로세스다. 화면이 앱 소유와 외부를 갈라 보여야 한다(FR-005). */
const OWNERS: Partial<Record<ManagedServiceId, "app" | "external">> = {};

function blank(id: ManagedServiceId): ManagedService {
  return {
    id,
    owner: OWNERS[id] ?? "app",
    displayName: DISPLAY_NAMES[id],
    state: "pending",
    stateReason: null,
    probeKind: null,
    lastProbeAt: null,
    lastProbeMs: null,
    restartCount: 0,
    restartGaveUpAt: null,
    version: null,
    endpoint: null,
  };
}

export interface RuntimeSnapshot {
  services: ManagedService[];
  capabilities: Capability[];
  graphGuard: GraphGuard | null;
  dockerAvailable: boolean | null;
  releaseId: string | null;
  legacyData: LegacyDataNotice | null;
  legacyStatus: ReturnType<typeof deriveLegacyStatus>;
}

/**
 * 감독 상태를 들고 있는 것. 프로세스 안에 사는 값이고 디스크에 안 쓴다 — 재기동하면
 * 처음부터 다시 잰다(옛 값을 믿는 것보다 싸고 정확하다).
 */
export class RuntimeRegistry {
  private services = new Map<ManagedServiceId, ManagedService>();
  private guard: GraphGuard | null = null;
  private docker: boolean | null = null;
  private release: string | null = null;
  private legacy: LegacyDataNotice | null = null;

  /** 감독 대상 목록을 정한다. **목록에 없는 서비스는 기능 파생에서 "모른다"가 된다.** */
  register(ids: ManagedServiceId[]): void {
    for (const id of ids) {
      if (!this.services.has(id)) this.services.set(id, blank(id));
    }
  }

  setEndpoint(id: ManagedServiceId, endpoint: string | null, version?: string | null): void {
    const service = this.services.get(id) ?? blank(id);
    this.services.set(id, { ...service, endpoint, version: version ?? service.version });
  }

  setGraphGuard(guard: GraphGuard | null): void {
    this.guard = guard;
  }

  setDockerAvailable(available: boolean | null): void {
    this.docker = available;
  }

  setReleaseId(releaseId: string | null): void {
    this.release = releaseId;
  }

  /**
   * 옛 구성에 남은 데이터 안내 (T049).
   *
   * `null` 은 **"아직 안 봤다"** 다 — "안내가 필요 없다"가 아니다. 렌더러가 둘을
   * 같은 화면으로 보여주면, 업그레이드한 사용자가 빈 프로젝트 목록을 보고
   * **데이터가 지워진 줄 안다.**
   */
  setLegacyData(notice: LegacyDataNotice | null): void {
    this.legacy = notice;
  }

  /**
   * 프로브 결과를 상태로 옮긴다.
   *
   * `facts.alive` 를 **모르면 `null` 로 넘긴다.** `false` 로 넘기면 "죽었다"가 되고,
   * 그건 모르는 것을 아는 척하는 것이다.
   */
  applyProbe(
    id: ManagedServiceId,
    facts: Omit<ServiceFacts, "health" | "capability"> & {
      health: ProbeResult | null;
      capability: ProbeResult | null;
    },
  ): void {
    const previous = this.services.get(id) ?? blank(id);
    const decision = decideState(facts);
    const latest = facts.capability ?? facts.health;
    this.services.set(id, {
      ...previous,
      state: decision.state,
      stateReason: decision.stateReason,
      probeKind: decision.probeKind,
      lastProbeAt: latest ? new Date().toISOString() : previous.lastProbeAt,
      lastProbeMs: latest ? latest.durationMs : previous.lastProbeMs,
    });
  }

  noteRestart(id: ManagedServiceId, gaveUp: boolean): void {
    const service = this.services.get(id) ?? blank(id);
    this.services.set(id, {
      ...service,
      restartCount: service.restartCount + 1,
      restartGaveUpAt: gaveUp ? new Date().toISOString() : service.restartGaveUpAt,
    });
  }

  snapshot(): RuntimeSnapshot {
    const services = [...this.services.values()];
    return {
      services,
      // **저장하지 않고 매번 파생한다.** 가드를 같이 넘기는 것이 T034 의 핵심이다.
      capabilities: deriveCapabilities(services, this.guard),
      graphGuard: this.guard,
      dockerAvailable: this.docker,
      releaseId: this.release,
      legacyData: this.legacy,
      legacyStatus: deriveLegacyStatus(services),
    };
  }

  /** 앞 스냅샷과 비교해 **바뀐 것만** 돌려준다. 안 바뀌면 빈 배열이다. */
  diff(before: ManagedService[]): ManagedServiceId[] {
    return changedServiceIds(before, [...this.services.values()]);
  }

  /** 프로브 종류별로 마지막에 무엇으로 판정했는지. 진단에 쓴다. */
  probeKindOf(id: ManagedServiceId): ProbeKind | null {
    return this.services.get(id)?.probeKind ?? null;
  }

  /** 감독 대상인가. **모르는 id 를 받으면 조용히 만들지 않는다** — 오타가 서비스가 된다. */
  knows(id: ManagedServiceId): boolean {
    return this.services.has(id);
  }

  /** 컨테이너로 도는 것들. `architect` 는 호스트 프로세스라 제외한다. */
  containerServiceIds(): ManagedServiceId[] {
    return [...this.services.keys()].filter((id) => id !== "architect");
  }

  /**
   * 사용자가 내린 것. `failed` 와 다르다 — **되살리기를 시도하지 않는다.**
   * 뭉치면 사용자가 끈 것을 앱이 다시 켜서 되살아난다.
   */
  markStopped(id: ManagedServiceId, reason: string): void {
    const service = this.services.get(id);
    if (!service) return;
    this.services.set(id, { ...service, state: "stopped", stateReason: reason, probeKind: null });
  }
}
