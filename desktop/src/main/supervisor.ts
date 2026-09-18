/**
 * 프로브 결과 → `ManagedService.state` (spec 058 T025).
 *
 * ## 이 파일의 규칙 하나
 *
 * **`probeKind: "health"` 만 통과한 서비스는 `ready` 가 아니다.**
 *
 * 09-17 실측이 근거다. `compose up --wait` 가 8/8 healthy 를 보고한 상태에서
 * pdf2bpmn 은 `/healthz` 200 을 내면서 생성 요청에 502 를 냈다. 그 상태를
 *
 *     ready    라고 부르면 화면이 "쓸 수 있다"고 거짓말한다
 *     failed   라고 부르면 컨테이너는 살아 있고 다른 경로는 쓸 수 있는데 다 막는다
 *
 * 둘 다 틀렸다. 그래서 `degraded` 가 있다 — **이 스펙의 핵심**이다.
 *
 * ## `error` 를 `fail` 로 뭉치지 않는다
 *
 * 프로브가 못 돌았으면(도구 없음·설정 없음) 그건 "안 된다"가 아니라 **"모른다"** 다.
 * 그 경우 상태를 `degraded`·`failed` 로 내리지 않고 `starting` 에 둔 뒤 이유를 적는다.
 * 뭉치면 사용자가 멀쩡한 서비스를 고치려 든다.
 */

import type {
  ManagedService,
  ManagedServiceId,
  ProbeResult,
  ServiceState,
} from "../shared/runtime-contract";

export interface ServiceFacts {
  /** 컨테이너/프로세스가 물리적으로 살아 있는가. 모르면 `null`. */
  alive: boolean | null;
  health: ProbeResult | null;
  capability: ProbeResult | null;
  /** 이 서비스에 기능 프로브가 정의돼 있는가. 없으면 health 만으로 `ready` 가 된다. */
  hasCapabilityProbe: boolean;
}

export interface StateDecision {
  state: ServiceState;
  stateReason: string | null;
  probeKind: ManagedService["probeKind"];
}

/**
 * 한 서비스의 상태를 정한다.
 *
 * 순서가 중요하다 — 아래로 갈수록 약한 근거다.
 */
export function decideState(facts: ServiceFacts): StateDecision {
  const { alive, health, capability, hasCapabilityProbe } = facts;

  // ① 물리적으로 죽었으면 그것이 가장 강한 사실이다. 프로브를 볼 필요가 없다.
  if (alive === false) {
    return { state: "failed", stateReason: "컨테이너/프로세스가 실행 중이 아닙니다.", probeKind: null };
  }

  // ② health 가 실패면 떠 있지 않은 것이다.
  if (health?.outcome === "fail") {
    return { state: "failed", stateReason: health.detail, probeKind: "health" };
  }

  // ③ health 를 못 쟀으면 **모른다.** 실패로 내리지 않는다.
  if (!health || health.outcome === "error") {
    return {
      state: "starting",
      stateReason: health ? `상태를 확인하지 못했습니다: ${health.detail}` : "아직 확인하지 않았습니다.",
      probeKind: health ? "health" : null,
    };
  }

  // 여기부터 health 는 pass 다. **그것만으로는 ready 가 아니다.**

  if (!hasCapabilityProbe) {
    // 기능 프로브가 없는 서비스는 health 가 판정의 전부다. 그 사실을 `probeKind` 로
    // 남긴다 — 나중에 "이건 무엇으로 통과한 거지"를 되물을 수 있어야 한다.
    return { state: "ready", stateReason: null, probeKind: "health" };
  }

  if (!capability) {
    return { state: "starting", stateReason: "기능 확인을 기다리고 있습니다.", probeKind: "health" };
  }

  switch (capability.outcome) {
    case "pass":
      return { state: "ready", stateReason: null, probeKind: "capability" };
    case "fail":
      // **떴지만 일할 수 없다.** 컨테이너는 살아 있으니 failed 가 아니다.
      return { state: "degraded", stateReason: capability.detail, probeKind: "capability" };
    case "skipped":
      return { state: "starting", stateReason: capability.detail, probeKind: "health" };
    case "error":
    default:
      // 못 쟀다. `degraded` 로 내리면 화면이 "고장났다"고 말하게 되는데 그건 모르는 것을
      // 아는 척하는 것이다.
      return {
        state: "starting",
        stateReason: `기능을 확인하지 못했습니다: ${capability.detail}`,
        probeKind: "health",
      };
  }
}

/**
 * 되살리기 한계에 도달한 서비스는 `stopped` 다 — 계속 `failed` 로 두면 화면이 영원히
 * "다시 시도 중"처럼 보인다. `stopped` 여도 사용자가 직접 부르는 길은 열려 있다(FR-018).
 */
export function applyRestartBudget(
  decision: StateDecision,
  restartCount: number,
  limit: number,
): StateDecision {
  if (decision.state !== "failed" || restartCount < limit) return decision;
  return {
    ...decision,
    state: "stopped",
    stateReason:
      `${decision.stateReason ?? "실패했습니다."} 자동 되살리기 ${restartCount}회가 모두 실패했습니다. ` +
      "런타임 상태에서 직접 다시 시도할 수 있습니다.",
  };
}

/**
 * 하위 호환 `status` 파생 — `ipc-contract.ts` 의 `RuntimeStatus`.
 *
 * **두 곳에 같은 사실을 두지 않는다.** `status` 는 저장하지 않고 `services` 에서
 * 매번 계산한다.
 */
export function deriveLegacyStatus(
  services: ManagedService[],
): "initializing" | "starting-db" | "starting-backend" | "ready" | "fatal" {
  const find = (id: ManagedServiceId) => services.find((service) => service.id === id);
  const architect = find("architect");
  if (!architect) return "initializing";
  if (architect.state === "failed" || architect.state === "stopped") return "fatal";
  if (architect.state === "starting" || architect.state === "pending") {
    const containers = services.filter((service) => service.id !== "architect");
    const containersReady = containers.every(
      (service) => service.state === "ready" || service.state === "degraded",
    );
    return containersReady ? "starting-backend" : "starting-db";
  }
  const others = services.filter((service) => service.id !== "architect");
  const broken = others.some((service) => service.state === "failed" || service.state === "stopped");
  return broken ? "starting-db" : "ready";
}

/** 바뀐 서비스만 골라낸다 — 화면이 알림을 한 번만 띄우려면 이것이 필요하다. */
export function changedServiceIds(
  before: ManagedService[],
  after: ManagedService[],
): ManagedServiceId[] {
  const previous = new Map(before.map((service) => [service.id, service]));
  return after
    .filter((service) => {
      const old = previous.get(service.id);
      return !old || old.state !== service.state || old.stateReason !== service.stateReason;
    })
    .map((service) => service.id);
}
