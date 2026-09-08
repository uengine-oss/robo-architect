/**
 * 산출물 문서의 머메이드 도식 정의 검사.
 *
 * 화면을 띄우지 않고 정의 문자열만 본다. 여기서 잡으려는 것은 **데이터가 어떤
 * 모양일 때 그림이 조용히 빠지는가** 이다 — 관계가 있는 데이터로 화면을 열면
 * 멀쩡해 보이므로 브라우저 검사로는 드러나지 않는다.
 *
 *   node scripts/verify-export-diagrams.mjs
 */
import { buildBcOverviewDef, buildContextMapDef, buildAggregateModelDef, mmdLabel }
  from '../frontend/src/features/exportDocument/diagrams.js'

let failed = 0
function check(name, cond, detail = '') {
  if (cond) { console.log(`  ok   ${name}`) }
  else { failed++; console.log(`  FAIL ${name}${detail ? ' — ' + detail : ''}`) }
}

const BCS = [
  { name: '휴가', domainType: 'Core Domain', aggregateCount: 2 },
  { name: '결재', domainType: 'Supporting Domain', aggregateCount: 1 },
  { name: '급여 연계', domainType: 'Generic Domain', aggregateCount: 1 },
]

console.log('\nBC 분해 결과')
{
  // 이것이 이 파일의 존재 이유다 — 관계가 하나도 없는 설계.
  const def = buildBcOverviewDef(BCS, [])
  const nodes = (def.match(/^\s+BC\d+\[/gm) || []).length
  check('관계가 없어도 BC 를 전부 그린다', nodes === BCS.length, `노드 ${nodes} / BC ${BCS.length}`)
  check('도메인 유형이 색으로 구분된다',
    def.includes('class BC0 core') && def.includes('class BC1 supporting') && def.includes('class BC2 generic'))

  const withRel = buildBcOverviewDef(BCS, [
    { fromBC: '휴가', toBC: '결재', policy: 'p1' },
    { fromBC: '휴가', toBC: '결재', policy: 'p2' },   // 같은 쌍은 한 번만
    { fromBC: '휴가', toBC: '휴가', policy: 'self' }, // 자기 자신은 긋지 않는다
    { fromBC: '없는BC', toBC: '결재', policy: 'x' },  // 모르는 이름은 무시
  ])
  const edges = (withRel.match(/^\s+BC\d+ --> BC\d+$/gm) || []).length
  check('중복·자기참조·미지의 BC 를 걸러 간선 하나만 남긴다', edges === 1, `간선 ${edges}`)
  check('BC 가 없으면 빈 정의', buildBcOverviewDef([], []) === '')
}

console.log('\n컨텍스트 간 연관 관계')
{
  check('관계가 없으면 그리지 않는다 (분해 결과와 역할이 다르다)', buildContextMapDef(BCS, []) === '')
  const def = buildContextMapDef(BCS, [
    { fromBC: '휴가', toBC: '결재', policy: '결재요청' },
    { fromBC: '휴가', toBC: '결재', policy: '반려처리' },
  ])
  check('같은 쌍의 Policy 는 한 간선에 모은다', (def.match(/-->\|/g) || []).length === 1)
  check('Policy 이름이 간선에 실린다', def.includes('결재요청') && def.includes('반려처리'))
}

console.log('\nAggregate 구조도')
{
  const AGGS = [
    {
      name: 'LeaveRequest', displayName: '휴가신청', rootEntity: 'LeaveRequest',
      properties: [{ name: 'id', isKey: true }, { name: 'days' }],
      enumerations: [{ name: 'Status', items: ['DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'CANCELED'] }],
      valueObjects: [{ name: 'ApproverRef', referencedAggregateName: 'ApprovalStep', referencedAggregateField: 'id', fields: [{ name: 'stepId' }] }],
    },
    { name: 'ApprovalStep', displayName: '결재단계', properties: [{ name: 'id', isKey: true }] },
  ]
  const def = buildAggregateModelDef(AGGS)
  check('Aggregate 마다 묶음을 만든다', (def.match(/^\s+subgraph SG\d+\[/gm) || []).length === 2)
  check('Enumeration 과 Value Object 를 매단다', def.includes('A0 --> A0E0') && def.includes('A0 --> A0V0'))
  check('경계를 넘는 참조를 점선으로 잇는다', /A0 -\.->\|"id"\| A1/.test(def))
  check('class 지정이 묶음 밖에 있다', def.indexOf('class A0 agg') > def.lastIndexOf('  end'))
  check('열거값이 많으면 줄인다', def.includes('…'))
  check('Aggregate 가 없으면 빈 정의', buildAggregateModelDef([]) === '')
}

console.log('\n라벨 이스케이프')
{
  check('따옴표를 바꾼다', mmdLabel('a "b" c') === "a 'b' c")
  check('줄바꿈을 없앤다', mmdLabel('a\nb') === 'a b')
  const def = buildBcOverviewDef([{ name: '따옴표 "있는" BC\n두 줄', domainType: 'Core Domain', aggregateCount: 0 }], [])
  check('정의 안에 따옴표가 새지 않는다', (def.match(/"/g) || []).length % 2 === 0)

  // 기준(local-msaez 81c9c5ca)이 밟은 것 — 가운뎃점 같은 유니코드 문장부호가 따옴표 밖에
  // 있으면 머메이드가 구문 오류를 낸다. 우리는 라벨을 늘 따옴표로 감싼다.
  const dot = buildBcOverviewDef([{ name: '연차 부여/소멸', domainType: 'Supporting Domain', aggregateCount: 3 }], [])
  check('가운뎃점·슬래시가 든 라벨을 따옴표로 감싼다', /BC0\["[^"]*·[^"]*"\]/.test(dot), dot.split('\n').find(l => l.includes('BC0[')))
}

console.log(failed === 0 ? '\n전부 통과\n' : `\n${failed}건 실패\n`)
process.exit(failed === 0 ? 0 : 1)
