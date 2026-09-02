/**
 * 템플릿 기반 코드 생성 — 렌더러.
 *
 * 렌더링을 브라우저에서 하는 이유는 하나다. **템플릿이 자기 Handlebars
 * 헬퍼를 JavaScript 로 들고 다닌다** — 파일 끝의 `<function>` 블록이다.
 * 서버(파이썬)로 옮기려면 그 JS 를 실행해야 하므로, 서버는 재료만 주고
 * 렌더링은 여기서 한다.
 *
 * 백엔드가 주는 것
 *   GET /api/code-templates/sets/{set}/files   forEach·path·fileName·body·functions
 *   GET /api/code-templates/context            boundedContexts·options·currentTimestamp
 */

import Handlebars from 'handlebars'

/** `forEach` 대상별 반복 목록. 템플릿이 고르는 여섯 가지다. */
export function itemsFor(forEach, ctx) {
  const bcs = ctx.boundedContexts || []
  const aggs = bcs.flatMap((b) => b.aggregates || [])
  const withOwner = (list, agg) =>
    (list || []).map((x) => ({ ...x, aggregate: agg, boundedContext: agg.boundedContext }))

  switch (forEach) {
    case 'BoundedContext': return bcs
    case 'Aggregate': return aggs
    case 'Command': return aggs.flatMap((a) => withOwner(a.commands, a))
    case 'Enumeration': return aggs.flatMap((a) => withOwner(a.enumerations, a))
    case 'ValueObject': return aggs.flatMap((a) => withOwner(a.valueObjects, a))
    case 'View': return bcs.flatMap((b) => b.views || [])
    default: return []
  }
}

/**
 * 기준 구현(`local-msaez` CodeGenerator)이 제공하는 기본 헬퍼.
 *
 * 템플릿이 `<function>` 으로 들고 오는 것과 별개로, 이 둘은 생성기가 준다는
 * 전제로 쓰인다 — 템플릿 어디에도 정의가 없다.
 */
function registerBaseHelpers(hb) {
  // `{{#attached 'View' this}}` — 요소에 붙은 하위 요소를 돈다.
  hb.registerHelper('attached', function (type, value, options) {
    const list = (value && value.attached) || []
    const matched = list.filter(
      (el) =>
        (el._type || '').endsWith(type) ||
        (type === 'ReadModel' && (el._type || '').endsWith('View')),
    )
    if (!matched.length) return options.inverse(this)
    return matched.map((item) => options.fn(item)).join('')
  })

  // `{{#outgoing 'Event' this}}` — 나가는 관계의 target 을 돈다.
  hb.registerHelper('outgoing', function (type, value, options) {
    const src = value == null ? this : value
    const matched = ((src && src.outgoingRelations) || []).filter(
      (r) => r && r.target && r.target.type === type,
    )
    if (!matched.length) return options.inverse(src)
    return matched.map((r) => options.fn(r.target)).join('')
  })

  hb.registerHelper('incoming', function (type, value, options) {
    const src = value == null ? this : value
    const matched = ((src && src.incomingRelations) || []).filter(
      (r) => r && r.source && r.source.type === type,
    )
    if (!matched.length) return options.inverse(src)
    return matched.map((r) => options.fn(r.source)).join('')
  })

  hb.registerHelper('equals', (a, b) => a === b)
}

/**
 * 템플릿이 들고 온 `<function>` 블록을 실행해 헬퍼를 등록한다.
 *
 * 블록은 `window.$HandleBars.registerHelper(...)` 를 부르고, 더러는
 * `this.contexts.<flag> = …` 로 렌더 스코프에 값을 심는다. 그래서 `window`
 * 와 `this` 를 모두 세워 준다. 한 블록이 죽어도 나머지는 등록되어야 하므로
 * 개별로 감싼다 — 실패는 삼키지 않고 돌려준다.
 */
export function registerHelpers(hb, sources, scope) {
  registerBaseHelpers(hb)
  const failures = []
  const win = { $HandleBars: hb, jp: undefined }
  for (const src of sources || []) {
    try {
      // eslint-disable-next-line no-new-func
      new Function('window', src).call(scope, win)
    } catch (e) {
      failures.push({ error: String((e && e.message) || e), source: src.slice(0, 120) })
    }
  }
  return failures
}

/**
 * `options` 와 `currentTimestamp` 를 중첩 객체까지 함께 실어 준다.
 *
 * **Handlebars 는 상위 스코프를 타지 않는다.** `{{#aggregateRoot.fieldDescriptors}}`
 * 안에서 `{{options.serviceId}}` 를 쓰면 필드에서만 찾고 없으면 빈 문자열이다
 * (`../options.serviceId` 로 써야 올라간다). 그런데 템플릿은 그냥 `{{options…}}`
 * 로 쓴다 — 기준 구현이 항목마다 실어 주기 때문이다. 여기서도 그렇게 한다.
 * 그러지 않으면 패키지가 `com.poscodx..autoDebitApplication` 이 된다.
 */
function withAmbient(node, ambient, seen = new WeakSet()) {
  if (Array.isArray(node)) return node.map((n) => withAmbient(n, ambient, seen))
  if (!node || typeof node !== 'object' || seen.has(node)) return node
  seen.add(node)
  const out = { ...ambient }
  for (const [k, v] of Object.entries(node)) out[k] = withAmbient(v, ambient, seen)
  return out
}

/**
 * 템플릿 묶음 전체를 렌더링한다.
 *
 * 반환은 `{ files, errors }`. 한 템플릿이 실패해도 나머지는 생성한다 —
 * 부분 결과가 없는 것보다 낫고, 무엇이 왜 빠졌는지는 `errors` 에 남는다.
 */
export function renderAll(templates, ctx, { dataProjection = 'cqrs' } = {}) {
  const hb = Handlebars.create()
  // `<function>` 블록이 심는 플래그가 여기로 들어온다.
  const scope = { contexts: {}, dataProjection }
  const helperFailures = registerHelpers(hb, (templates || []).flatMap((t) => t.functions || []), scope)

  const files = []
  const errors = [...helperFailures.map((f) => ({ template: '<function>', ...f }))]

  for (const t of templates || []) {
    if (!t.forEach) continue
    for (const item of itemsFor(t.forEach, ctx)) {
      const model = withAmbient(
        { ...item, ...scope.contexts },
        { options: ctx.options, currentTimestamp: ctx.currentTimestamp },
      )
      try {
        const dir = t.path ? hb.compile(t.path)(model) : ''
        const name = t.fileName
          ? hb.compile(t.fileName)(model)
          : t.relativePath.split('/').pop()
        files.push({
          path: [dir, name].filter(Boolean).join('/'),
          content: hb.compile(t.body || '')(model),
          template: t.relativePath,
          forEach: t.forEach,
        })
      } catch (e) {
        errors.push({
          template: t.relativePath,
          forEach: t.forEach,
          item: item.name || item.namePascalCase || '',
          error: String((e && e.message) || e),
        })
      }
    }
  }
  return { files, errors }
}
