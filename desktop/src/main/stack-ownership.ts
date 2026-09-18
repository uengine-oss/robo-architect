/**
 * 어느 컨테이너가 **우리 것인가**, 그리고 이미 떠 있으면 어떻게 하는가
 * (spec 058 T038·T039 · US3).
 *
 * ## 이름·포트로 고르지 않는다
 *
 * 사용자가 같은 이미지를 자기 손으로 따로 띄워 둘 수 있다. 이름이 겹치거나 포트가
 * 같다는 이유로 그것을 "우리 것"으로 보면, 앱이 남의 컨테이너를 내리거나 남의
 * 저장소에 쓴다. 판단은 **compose 가 붙인 라벨**로 한다.
 *
 * ```
 * org.uengine.robo.release     이 릴리스가 소유한다
 * org.uengine.robo.component   어느 서비스인가
 * ```
 *
 * ## 이미 떠 있는 것이 **정상이다**
 *
 * compose 가 `restart: unless-stopped` 라서, OS 를 재시작하면 앱보다 컨테이너가 먼저
 * 뜬다. 2026-09-18 에 실제로 그랬다 — 기계가 재부팅됐고 Docker Desktop 을 켜자 9개 중
 * 8개가 스스로 돌아왔다. 그 상태에서 앱이 "안 떠 있으니 띄운다"로 움직이면 중복이
 * 생긴다. **이어받는다.**
 *
 * ## 그리고 돌아오지 않는 것도 있다
 *
 * 같은 재부팅에서 두 컨테이너는 안 돌아왔다.
 *
 * ```
 * exit 127   사라진 호스트 경로를 바인드 마운트하고 있었다 (파일이 없어 명령이 못 돈다)
 * 재시작 정책 없음   `docker run` 으로 손으로 띄운 것
 * ```
 *
 * 그래서 "라벨이 붙은 컨테이너가 있다"와 "그게 돌고 있다"는 다른 사실이다. 이어받기는
 * **running 인 것만** 대상으로 하고, 멈춰 있는 것은 compose 가 다시 올리게 한다.
 */

import { execFile } from "node:child_process";

import type { ManagedServiceId } from "../shared/runtime-contract";

export const RELEASE_LABEL = "org.uengine.robo.release";
export const COMPONENT_LABEL = "org.uengine.robo.component";

export interface OwnedContainer {
  id: string;
  name: string;
  /** compose 의 `org.uengine.robo.component` 값. 서비스 id 와 **같지 않을 수 있다.** */
  component: string;
  running: boolean;
  /** `healthy` \| `unhealthy` \| `starting` \| `none`. 준비의 근거로 쓰지 않는다. */
  health: string;
  exitCode: number;
  image: string;
}

function run(args: string[], timeoutMs = 20_000): Promise<{ code: number; out: string }> {
  return new Promise((resolve) => {
    execFile("docker", args, { timeout: timeoutMs, encoding: "utf8" }, (error, stdout, stderr) => {
      const out = `${stdout ?? ""}${stderr ?? ""}`;
      const code = error
        ? typeof (error as { code?: unknown }).code === "number"
          ? (error as { code: number }).code
          : 1
        : 0;
      resolve({ code, out });
    });
  });
}

/**
 * 이 릴리스가 소유한 컨테이너 전부. **멈춘 것도 포함한다** — 멈춰 있다는 사실이
 * 이어받기 판단에 필요하다.
 *
 * 못 물어봤으면 `null` 을 돌려준다. **빈 배열로 돌려주면 "우리 것이 하나도 없다"가
 * 되어 앱이 전부 새로 띄운다** — 중복이 생기는 자리가 정확히 거기다.
 */
export async function listOwnedContainers(releaseId: string): Promise<OwnedContainer[] | null> {
  const { code, out } = await run([
    "ps",
    "--all",
    "--filter",
    `label=${RELEASE_LABEL}=${releaseId}`,
    "--format",
    "{{.ID}}",
  ]);
  if (code !== 0) return null;
  const ids = out.trim().split("\n").map((line) => line.trim()).filter(Boolean);
  if (ids.length === 0) return [];

  const format =
    `{{.Id}}\t{{.Name}}\t{{index .Config.Labels "${COMPONENT_LABEL}"}}\t` +
    "{{.State.Running}}\t{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}\t" +
    "{{.State.ExitCode}}\t{{.Config.Image}}";
  const inspected = await run(["inspect", "--format", format, ...ids]);
  if (inspected.code !== 0) return null;

  const containers: OwnedContainer[] = [];
  for (const line of inspected.out.trim().split("\n")) {
    const parts = line.split("\t");
    if (parts.length < 7) continue;
    containers.push({
      id: parts[0]!,
      name: parts[1]!.replace(/^\//, ""),
      component: parts[2]!,
      running: parts[3] === "true",
      health: parts[4]!,
      exitCode: Number(parts[5]) || 0,
      image: parts[6]!,
    });
  }
  return containers;
}

export interface AdoptionPlan {
  /** 이미 돌고 있어 **그대로 쓸** 것. */
  adopt: OwnedContainer[];
  /** 라벨은 우리 것인데 멈춰 있어 compose 가 다시 올려야 하는 것. */
  restart: OwnedContainer[];
  /** 아직 컨테이너조차 없는 서비스. */
  missing: ManagedServiceId[];
  /**
   * `compose up` 을 불러야 하는가.
   *
   * **하나라도 없거나 멈춰 있으면 부른다.** compose 는 이미 맞게 돌고 있는 것을
   * 건드리지 않으므로(`up` 은 수렴이다) 전부 살아 있을 때만 건너뛴다.
   */
  needsUp: boolean;
  /** 못 물어봤다. 이 경우 **띄우지도 이어받지도 말고 사람에게 알린다.** */
  unknown: boolean;
  reason: string;
}

/**
 * 이어받기 계획. 순수 함수 — 목록을 주면 무엇을 할지 정한다.
 *
 * `components` 는 서비스 id → compose component 이름이다. 둘이 같지 않은 자리가
 * 있다(`graph` → `graph-bolt`·`graph-db`). 그 표를 밖에서 받는다.
 */
export function planAdoption(
  containers: OwnedContainer[] | null,
  components: ReadonlyArray<{ id: ManagedServiceId; component: string }>,
): AdoptionPlan {
  if (containers === null) {
    return {
      adopt: [],
      restart: [],
      missing: [],
      needsUp: false,
      // **모르면 띄우지 않는다.** 여기서 "없는 것 같으니 띄우자"로 가면 중복이 생긴다.
      unknown: true,
      reason: "컨테이너 목록을 확인하지 못했습니다. 실행 환경을 먼저 확인하세요.",
    };
  }

  const byComponent = new Map(containers.map((container) => [container.component, container]));
  const adopt: OwnedContainer[] = [];
  const restart: OwnedContainer[] = [];
  const missing: ManagedServiceId[] = [];

  for (const { id, component } of components) {
    const container = byComponent.get(component);
    if (!container) {
      missing.push(id);
      continue;
    }
    (container.running ? adopt : restart).push(container);
  }

  const needsUp = restart.length > 0 || missing.length > 0;
  const parts: string[] = [];
  if (adopt.length > 0) parts.push(`이미 실행 중 ${adopt.length}개를 이어받습니다`);
  if (restart.length > 0) parts.push(`멈춘 ${restart.length}개를 다시 올립니다`);
  if (missing.length > 0) parts.push(`없는 ${missing.length}개를 새로 띄웁니다`);
  return {
    adopt,
    restart,
    missing,
    needsUp,
    unknown: false,
    reason: parts.join(" · ") || "모든 서비스가 이미 실행 중입니다",
  };
}

/**
 * **다른 릴리스가 남긴 우리 컨테이너**를 찾는다 — 업그레이드 뒤에 옛 릴리스의
 * 컨테이너가 포트를 쥐고 있으면 새 것이 못 뜬다.
 *
 * 지우지 않는다. **찾아서 알린다** — 지우는 것은 사용자가 결정한다(데이터가 딸린
 * 볼륨이 붙어 있을 수 있다).
 */
export async function listStaleReleases(currentReleaseId: string): Promise<string[] | null> {
  const { code, out } = await run([
    "ps",
    "--all",
    "--filter",
    `label=${RELEASE_LABEL}`,
    "--format",
    `{{index .Labels "${RELEASE_LABEL}"}}`,
  ]);
  if (code !== 0) return null;
  const others = new Set(
    out
      .trim()
      .split("\n")
      .map((line) => line.trim())
      .filter((value) => value && value !== currentReleaseId),
  );
  return [...others].sort();
}
