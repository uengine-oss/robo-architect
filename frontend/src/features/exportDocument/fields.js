/**
 * 노드의 **필드 목록**을 꺼낸다 — 어느 칸에 들어 있든.
 *
 * ## 왜 따로 있나 (2026-10-08)
 *
 * 내보낸 문서의 Event 표에서 **Payload 가 26행 전부 `-`** 였다. "필드를 안 만들었나"
 * 싶었지만 아니었다 — 재 보니 이렇다.
 *
 * ```
 * payload      0/26 · 전부 null        ← 내보내기가 읽던 칸
 * properties  26/26 · 필드 2~32개씩    ← 실제 필드가 여기 있다
 * ```
 *
 * 즉 **이름표가 어긋나 조용히 비어 나갔다.** 오류도 안 났다 — `null` 을 풀면 빈
 * 배열이고, 빈 배열은 `-` 로 찍히고, `-` 는 "없다" 로 읽힌다. Command 는 같은 자리에
 * `inputSchema` 가 채워져 있어 **17/17 멀쩡했다**. 그래서 한쪽만 비었고, 그 차이가
 * 눈에 띄기까지 오래 걸렸다.
 *
 * 꺼내는 자리를 한 군데로 모아, 다음에 이름표가 하나 더 생겨도 **한 곳만** 고치게 한다.
 */

/** `{"approvalStepId": "string", ...}` 꼴 JSON 문자열/객체를 필드 목록으로. */
export function parseJsonFields(json) {
  if (!json) return []
  try {
    const obj = typeof json === 'string' ? JSON.parse(json) : json
    if (!obj || typeof obj !== 'object') return []
    if (Array.isArray(obj)) return normalizeFields(obj)
    return Object.entries(obj).map(([k, v]) => ({
      name: k,
      type: typeof v === 'string' ? v : JSON.stringify(v),
    }))
  } catch {
    return []
  }
}

/**
 * 배열로 온 필드를 **쓰는 쪽이 아는 모양**으로 맞추고, **같은 것을 한 번만** 남긴다.
 *
 * 2026-10-08 — `/api/contexts/{id}/full-tree` 가 한 Event 의 필드를 **2~4배로** 돌려줬다
 * (`UNWIND $parent_ids` 에 같은 id 가 여러 번 들어갔다). 그래서 문서의 Payload 에
 * `approvalLineId(String)` 이 네 번 찍혔다. 라우터를 고쳤지만 여기서도 떨어낸다 —
 * **문서는 어느 경로로 들어온 값이든 같은 필드를 두 번 적어서는 안 된다.**
 */
function normalizeFields(list) {
  const seen = new Set()
  const out = []
  for (const f of list || []) {
    if (!f || !(f.name || f.displayName)) continue
    const field = {
      name: f.name || f.displayName,
      type: f.type || f.dataType || 'String',
      isKey: Boolean(f.isKey),
      isRequired: Boolean(f.isRequired),
      description: f.description || '',
    }
    // id 가 있으면 그것이 같음의 기준이다. 없으면 이름으로 가른다 —
    // 한 부모 안에 같은 이름의 필드가 둘 있는 설계는 없다.
    const key = f.id || `name:${field.name}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(field)
  }
  return out
}

/**
 * 그 노드의 필드 — **`properties` 가 원본**이고, 없으면 JSON 칸을 푼다.
 *
 * `extra` 는 그 노드 종류의 JSON 칸 이름이다(Event 는 `payload`,
 * Command 는 `inputSchema`). 둘 다 비면 빈 배열이고, 그때는 부르는 쪽이
 * `-` 를 쓸지 정한다.
 */
export function fieldsOf(node, extra) {
  if (!node) return []
  const props = normalizeFields(node.properties)
  if (props.length) return props
  for (const key of extra ? [extra] : ['payload', 'inputSchema', 'fields']) {
    const got = parseJsonFields(node[key])
    if (got.length) return got
  }
  return []
}
