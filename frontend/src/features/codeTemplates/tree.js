/**
 * 평평한 생성 결과(`[{path, content}]`)를 디렉터리 트리로 접는다.
 *
 * 생성물은 디스크에 없다 — 메모리에만 있는 미리보기다. 그래서 Claude Code 탭의
 * FileTreePane 을 그대로 쓸 수 없다(그쪽은 경로를 서버에 물어본다).
 */

/**
 * @param {{path:string}[]} files
 * @returns {{name:string, path:string, dir:boolean, children?:any[], file?:object}[]}
 */
export function buildTree(files) {
  const root = { children: new Map() }

  for (const file of files || []) {
    const parts = file.path.split('/').filter(Boolean)
    let node = root
    parts.forEach((part, i) => {
      const last = i === parts.length - 1
      if (!node.children.has(part)) {
        node.children.set(part, {
          name: part,
          path: parts.slice(0, i + 1).join('/'),
          dir: !last,
          children: new Map(),
        })
      }
      node = node.children.get(part)
      if (last) {
        node.dir = false
        node.file = file
      }
    })
  }

  // 디렉터리 먼저, 그다음 이름 순. 자바 트리는 깊어서 순서가 없으면 못 읽는다.
  const toArray = (n) =>
    [...n.children.values()]
      .sort((a, b) => (a.dir === b.dir ? a.name.localeCompare(b.name) : a.dir ? -1 : 1))
      .map((c) => (c.dir ? { ...c, children: toArray(c) } : { ...c, children: [] }))

  return toArray(root)
}

/**
 * 자식이 하나뿐인 디렉터리들을 한 줄로 합친다 — `src/main/java/com/poscodx/…`
 * 를 한 칸씩 펼치게 두면 트리가 화면을 다 먹는다. IDE 의 "compact folders" 다.
 */
export function collapseChains(nodes) {
  return (nodes || []).map((n) => {
    if (!n.dir) return n
    let node = n
    let name = n.name
    while (node.children.length === 1 && node.children[0].dir) {
      node = node.children[0]
      name += '/' + node.name
    }
    return { ...node, name, children: collapseChains(node.children) }
  })
}

/** 트리에서 처음 만나는 파일 — 생성 직후 무엇이든 보여 주려고 쓴다. */
export function firstFile(nodes) {
  for (const n of nodes || []) {
    if (!n.dir) return n.file
    const found = firstFile(n.children)
    if (found) return found
  }
  return null
}
