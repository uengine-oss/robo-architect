// Proposal 영구 삭제 확인 — 입력한 값이 id 와 같을 때만 삭제를 켠다.
//
// 되돌릴 수 없는 작업이라 **엄격 일치**는 그대로다(대소문자·부분 일치 허용 안 함).
// 앞뒤 공백만 걷는다 — 복사·붙여넣기에서 따라 들어오는 개행/공백 때문에
// "보이는 값은 같은데 안 켜지는" 일을 없앤다.
export function normalizeDeleteConfirm(input) {
  return String(input ?? '').trim()
}

export function deleteConfirmMatches(input, id) {
  if (!id) return false
  return normalizeDeleteConfirm(input) === String(id)
}
