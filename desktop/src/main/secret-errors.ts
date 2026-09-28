/**
 * 비밀 저장소가 내는 **사람이 읽는 오류** (ENT-APP-002).
 *
 * ## 왜 별도 파일인가
 *
 * `secret-store.ts` 는 `electron` 을 끌고 온다(`safeStorage`). 그 안에 두면 이
 * 메시지를 단위 테스트로 부를 수 없고, 소스 문자열을 읽어 재는 우회 검사밖에
 * 남지 않는다. 메시지 자체가 이 수정의 알맹이라 실제로 불러서 잰다.
 */

/**
 * 암호문은 있는데 **열 수가 없다.**
 *
 * `safeStorage` 는 암호문을 파일에 두고 그 **키는 따로** 둔다(Windows 는
 * `<dataDir>\Local State` 안, DPAPI 로 사용자 계정에 묶임). 그래서 둘 중 하나만
 * 남으면 이 상태가 된다 — 재설치, PC 이전, Windows 계정 변경, `Local State` 만
 * 빠뜨린 백업.
 *
 * **데이터가 사라진 것이 아니다.** 볼륨은 멀쩡하고 앱만 못 붙는다. 그런데 예전에는
 * 드라이버 원문이 그대로 사용자에게 떴다 —
 *
 *     Error while decrypting the ciphertext provided to safeStorage.decryptString.
 *
 * 무엇이 잘못됐는지도, 무엇을 해야 하는지도 알 수 없었다. 2026-09-28 설치 검증에서
 * 실제로 겪었고, 백업에 `Local State` 를 빠뜨린 것이 원인이었다.
 *
 * **자동으로 새로 뽑지 않는다.** 그래프 비밀번호를 말없이 갈아치우면 기존 볼륨에
 * 붙지 못하는 것은 똑같은데 원인이 더 안 보이게 된다. 사람이 고르게 한다.
 */
export class SecretUndecryptableError extends Error {
  readonly code = "secret_store.undecryptable";

  constructor(
    readonly secretId: string,
    readonly file: string,
    cause?: unknown,
  ) {
    super(buildMessage(secretId, file));
    this.name = "SecretUndecryptableError";
    if (cause !== undefined) this.cause = cause;
  }
}

/**
 * 메시지가 갖춰야 할 것 넷 — **무엇이·왜·데이터는 어떤지·무엇을 할지.**
 * 하나라도 빠지면 사용자는 앱을 지우거나 포기한다.
 */
export function buildMessage(secretId: string, file: string): string {
  return (
    `비밀 저장소를 열 수 없습니다 (${secretId}). ` +
    "암호문은 있는데 그것을 푸는 키가 바뀌었습니다 — 앱을 다시 설치했거나, " +
    "PC·Windows 계정을 옮겼거나, 백업에 'Local State' 를 빠뜨린 경우입니다. " +
    "데이터는 지워지지 않았습니다 — 그래프 볼륨은 그대로이고 앱만 붙지 못합니다. " +
    `복구 절차는 app-operations.md 의 '백업' 절을 보세요. 파일: ${file}`
  );
}
