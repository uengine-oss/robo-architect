/**
 * 프로브를 **주기적으로 돌리는 것** (spec 058 T018).
 *
 * ## 왜 이 파일이 늦게 생겼나
 *
 * 058 은 프로브(`probes/`)와 판정(`supervisor.ts`)을 먼저 만들었다. 그런데
 * **둘을 돌려 주는 것이 없었다** — `RuntimeRegistry.applyProbe` 의 호출자가
 * 2026-10-07 측정 시점까지 **0개**였다. 그래서
 *
 *     snapshot().services  는 언제나 빈 배열이고
 *     buildRuntimeState()  은 "등록이 비어 있으면 신규 필드를 안 싣는다" 로 빠지고
 *     화면은 예전처럼 **백엔드 상태 하나**만 본다
 *
 * 즉 서비스 9개를 따로 보는 설계가 **코드로는 있고 동작으로는 없었다.** 이
 * 파일이 그 간격을 메운다.
 *
 * ## 주기를 둘로 가르는 이유
 *
 * ```
 * health      5초   싸다(포트·HTTP 한 번). 죽은 것을 빨리 알아야 한다
 * capability  60초  비싸다(컨테이너 exec·실제 기능 호출). 자주 돌릴 것이 아니다
 * ```
 *
 * **health 만 통과한 서비스는 `ready` 가 아니다**(`supervisor.decideState`).
 * 그러니 capability 가 한 번 돌기 전까지 그 서비스는 `starting` 에 머문다 —
 * 그것이 맞다. "열렸으니 됐다" 고 말했다가 502 를 받은 것이 이 스펙의 출발점이다.
 *
 * ## 이 파일이 **하지 않는** 것
 *
 * 렌더러에 새 채널로 밀지 않는다(T019). 지금은 **등록에 채워 넣고 변화만
 * 기록한다** — `app:getRuntimeState` 가 이미 `services` 를 실어 주므로 그것으로
 * 보이고, 로그(`runtime.service.state`)로 측정된다. 새 채널과 화면은 T019·T027
 * 의 몫이고, 그것을 여기서 미리 만들면 **쓰는 쪽 없는 채널**이 하나 더 생긴다.
 */

import type {
  ManagedServiceId,
  ProbeKind,
  ProbeResult,
} from "../shared/runtime-contract";

/** 싼 프로브. 죽은 것을 빨리 알기 위한 간격이다. */
export const HEALTH_INTERVAL_MS = 5_000;
/** 비싼 프로브. 실제 기능을 건드리므로 드물게 돈다. */
export const CAPABILITY_INTERVAL_MS = 60_000;
/** 계획을 다시 세우는 간격. 프로브 간격보다 촘촘해야 제때 돈다. */
export const TICK_MS = 1_000;

export interface Due {
  id: ManagedServiceId;
  kind: ProbeKind;
}

export interface DueOptions {
  hasCapability(id: ManagedServiceId): boolean;
  healthMs?: number;
  capabilityMs?: number;
  /** 아직 돌고 있는 `${id}:${kind}`. **겹쳐 돌리지 않는다.** */
  inflight?: ReadonlySet<string>;
}

export const probeKey = (id: ManagedServiceId, kind: ProbeKind): string => `${id}:${kind}`;

/**
 * 지금 돌려야 할 프로브 목록. **순수 함수다** — 시계와 지난 기록만 본다.
 *
 * 한 번도 안 돈 것은 바로 돈다(`undefined` 를 0 으로 보지 않는다 — 0 은 1970년이고
 * "안 돌았다" 와 뜻이 다르다. 여기서는 결과가 같지만, 뜻이 다른 둘을 같은 값으로
 * 쓰면 다음 사람이 그 위에 조건을 얹을 때 틀린다).
 */
export function duePlan(
  ids: readonly ManagedServiceId[],
  lastRun: ReadonlyMap<string, number>,
  now: number,
  options: DueOptions,
): Due[] {
  const healthMs = options.healthMs ?? HEALTH_INTERVAL_MS;
  const capabilityMs = options.capabilityMs ?? CAPABILITY_INTERVAL_MS;
  const inflight = options.inflight ?? new Set<string>();
  const out: Due[] = [];
  for (const id of ids) {
    const kinds: [ProbeKind, number][] = [["health", healthMs]];
    if (options.hasCapability(id)) kinds.push(["capability", capabilityMs]);
    for (const [kind, interval] of kinds) {
      const key = probeKey(id, kind);
      if (inflight.has(key)) continue;
      const last = lastRun.get(key);
      if (last === undefined || now - last >= interval) out.push({ id, kind });
    }
  }
  return out;
}

/**
 * `docker ps` 한 번의 결과에서 **이 서비스가 살아 있는가**를 읽는다.
 *
 * 후보 이름을 여러 개 받는 이유는 구성마다 컨테이너 이름이 다르기 때문이다
 * (`graph-bolt` ↔ `neo4j`). 하나라도 돌고 있으면 살아 있다.
 *
 * **이름을 못 찾았을 때 `false` 가 아니라 `null` 을 준다.** 우리가 이름을 틀렸을
 * 수도 있고, 그때 `false` 라고 말하면 `decideState` 가 가장 강한 근거로 받아
 * **멀쩡한 서비스를 "실행 중이 아닙니다" 로 덮는다.**
 */
/**
 * 컨테이너 이름에서 **서비스 토막**만 뽑는다 — `robo-architect-desktop-fabric-1` → `fabric`.
 *
 * compose 가 짓는 이름은 `<프로젝트>-<서비스>-<번호>` 다. 프로젝트 이름은 설치
 * 구성에 따라 바뀌므로 그 부분으로는 비교할 수 없다.
 */
function serviceToken(name: string): string {
  const parts = name.split("-").filter(Boolean);
  if (parts.length < 2) return "";
  // 마지막이 번호면 떼고, 그 앞 한 토막이 서비스다.
  const last = parts[parts.length - 1] ?? "";
  const end = /^\d+$/.test(last) ? parts.length - 1 : parts.length;
  return parts[end - 1] ?? "";
}

export function aliveFrom(
  running: readonly string[],
  candidates: readonly string[],
): boolean | null {
  if (running.length === 0) return null; // 목록 자체를 못 얻었다 — 모른다
  if (candidates.length === 0) return null;
  const set = new Set(running);
  if (candidates.some((name) => set.has(name))) return true;
  // 목록은 얻었고 후보가 그 안에 없다. 그런데 **접두사가 다를 뿐**일 수 있다 —
  // compose 프로젝트 이름이 바뀌면 `robo-pdf2bpmn-1` 이 `other-pdf2bpmn-1` 이 된다.
  // 그때 `false` 라고 말하면 멀쩡한 서비스를 "실행 중이 아닙니다" 로 덮으므로,
  // **같은 서비스 토막이 돌고 있으면 모른다**로 둔다.
  const sameToken = candidates.some((name) => {
    const token = serviceToken(name);
    return token.length > 0 && running.some((live) => serviceToken(live) === token);
  });
  return sameToken ? null : false;
}

export interface SupervisionDeps<Context> {
  /** 프로브가 정의된 서비스들. */
  ids(): ManagedServiceId[];
  hasCapability(id: ManagedServiceId): boolean;
  /** 프로브에 필요한 설정. **아직 모르면 `null`** — 그 틱은 아무것도 하지 않는다. */
  context(): Promise<Context | null>;
  probe(context: Context, id: ManagedServiceId, kind: ProbeKind): Promise<ProbeResult>;
  /** 돌고 있는 컨테이너 이름 전부. 못 얻으면 빈 배열(= 모른다). */
  running(): Promise<string[]>;
  containerNames(context: Context, id: ManagedServiceId): string[];
  /** 결과를 등록에 옮긴다(`RuntimeRegistry.applyProbe`). */
  apply(
    id: ManagedServiceId,
    facts: {
      alive: boolean | null;
      health: ProbeResult | null;
      capability: ProbeResult | null;
      hasCapabilityProbe: boolean;
    },
  ): void;
  /** 등록을 비교해 **바뀐 것만** 알려 준다(`RuntimeRegistry.diff`). */
  changed(): { id: ManagedServiceId; state: string; stateReason: string | null }[];
  /** 처음 한 번, 볼 서비스들을 등록해 둔다(`RuntimeRegistry.register`). */
  register(ids: ManagedServiceId[]): void;
  log(level: "info" | "warn", event: string, params: Record<string, unknown>): void;
  now?(): number;
}

export interface Supervision {
  /** 한 번 돌린다. 검사에서는 이것만 부른다(타이머 없이). */
  tick(): Promise<void>;
  stop(): void;
}

/**
 * 감독을 시작한다. 타이머는 **틱 하나**이고, 무엇을 돌릴지는 `duePlan` 이 정한다.
 *
 * 프로브가 느려도 틱은 계속 온다. 그래서 `inflight` 로 **같은 프로브를 겹쳐
 * 돌리지 않는다** — 겹치면 60초 프로브가 1초마다 쌓여 컨테이너를 때린다.
 */
export function startSupervision<Context>(
  deps: SupervisionDeps<Context>,
  options: { tickMs?: number; healthMs?: number; capabilityMs?: number; autostart?: boolean } = {},
): Supervision {
  const now = deps.now ?? (() => Date.now());
  const lastRun = new Map<string, number>();
  const inflight = new Set<string>();
  const latest = new Map<
    ManagedServiceId,
    { health: ProbeResult | null; capability: ProbeResult | null }
  >();
  let registered = false;
  let timer: ReturnType<typeof setInterval> | null = null;
  let stopped = false;

  async function tick(): Promise<void> {
    if (stopped) return;
    const context = await deps.context();
    if (context === null) return; // 설정을 아직 모른다 — 추측해서 재지 않는다
    const ids = deps.ids();
    if (!registered && ids.length > 0) {
      deps.register(ids);
      registered = true;
    }
    const plan = duePlan(ids, lastRun, now(), {
      hasCapability: deps.hasCapability,
      healthMs: options.healthMs,
      capabilityMs: options.capabilityMs,
      inflight,
    });
    if (plan.length === 0) return;

    const running = await deps.running().catch(() => [] as string[]);
    for (const { id, kind } of plan) inflight.add(probeKey(id, kind));
    await Promise.all(
      plan.map(async ({ id, kind }) => {
        try {
          const result = await deps.probe(context, id, kind);
          const slot = latest.get(id) ?? { health: null, capability: null };
          latest.set(id, { ...slot, [kind]: result });
        } catch (error) {
          // `runProbe` 는 스스로 안 던진다(예외를 `outcome: "error"` 로 돌려준다).
          // 그래도 **한 프로브의 사고가 다른 서비스의 판정을 막지 않게** 받는다 —
          // 여기서 던지면 `Promise.all` 이 끊겨 나머지 서비스는 이 틱에 아예
          // 적용되지 않는다. 앞 결과는 지우지 않는다(모르는 것을 지우면 퇴보다).
          deps.log("warn", "runtime.supervision.probe_failed", {
            service: id,
            kind,
            message: error instanceof Error ? error.message : String(error),
          });
        } finally {
          lastRun.set(probeKey(id, kind), now());
          inflight.delete(probeKey(id, kind));
        }
      }),
    );

    // 판정은 **모든 결과를 모은 뒤** 한 번에 한다 — health 와 capability 가 따로
    // 적용되면 같은 틱 안에서 상태가 두 번 뒤집혀 로그가 거짓 변화를 남긴다.
    // 같은 서비스가 계획에 둘(health·capability) 들어 있으므로 **id 를 모은다.**
    for (const id of new Set(plan.map((item) => item.id))) {
      const slot = latest.get(id) ?? { health: null, capability: null };
      deps.apply(id, {
        alive: aliveFrom(running, deps.containerNames(context, id)),
        health: slot.health,
        capability: slot.capability,
        hasCapabilityProbe: deps.hasCapability(id),
      });
    }

    for (const service of deps.changed()) {
      deps.log("info", "runtime.service.state", {
        service: service.id,
        state: service.state,
        reason: service.stateReason,
      });
    }
  }

  if (options.autostart !== false) {
    timer = setInterval(() => {
      void tick().catch((error) => {
        deps.log("warn", "runtime.supervision.tick_failed", {
          message: error instanceof Error ? error.message : String(error),
        });
      });
    }, options.tickMs ?? TICK_MS);
    // 타이머가 앱 종료를 붙잡지 않게 한다 — 감독은 앱보다 오래 살 이유가 없다.
    timer.unref?.();
  }

  return {
    tick,
    stop() {
      stopped = true;
      if (timer) clearInterval(timer);
      timer = null;
    },
  };
}
