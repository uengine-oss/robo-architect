// 매뉴얼용 화면 캡처 경로. 회귀 시험으로 돌릴 때는 저장소의 문서 그림을 덮어쓰지 않도록
// test-results/manual-shots/<name> 에 쓰고, 문서 그림을 새로 찍을 때만(UPDATE_MANUAL_SHOTS=1) 문서 폴더에 쓴다.
// 경로는 frontend/ 기준(플레이라이트 실행 위치).
export function shotDir(docsDir: string, name: string): string {
  return process.env.UPDATE_MANUAL_SHOTS ? docsDir : `test-results/manual-shots/${name}`
}
