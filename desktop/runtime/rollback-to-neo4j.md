# 저장소를 Neo4j 구성으로 되돌리는 길 (spec 058 T079 · FR-024)

> 2026-09-17. 설치본의 graph 저장소를 `neo4j:5.26.0` → Ontological(`graph-db` +
> `graph-bolt`) 로 바꿨다. **교체가 현장에서 실패했을 때 이전 정상 상태로 갈 수
> 있어야 한다.** 이 문서가 그 길이다.

## 0. 먼저 알아야 할 것 — 데이터는 두 군데에 따로 있다

두 구성은 **볼륨이 다르다.**

```
Neo4j 구성        <프로젝트>_neo4j_data · <프로젝트>_neo4j_logs
Ontological 구성  <프로젝트>_graph_data
```

그래서 교체해도 **Neo4j 쪽 데이터는 지워지지 않는다.** 되돌리면 교체 직전 상태가
그대로 돌아온다. 반대로 **Ontological 위에서 만든 것은 되돌리면 안 보인다** —
`graph_data` 볼륨에 남아 있을 뿐이다. 되돌리기는 복구지 병합이 아니다.

> 실측(2026-09-17, 맥): Neo4j 스택에 `:ZzRollback` 4건을 심고, 컨테이너를 **지운 뒤**
> 같은 볼륨으로 새로 띄웠다. 이름 4개가 그대로 돌아왔다 — 개수가 아니라 **내용**으로
> 확인했다. 같은 라벨이 Ontological 스택에는 없었다(저장소가 갈려 있다는 증거).

## 1. 되돌리는 절차

```
① 앱을 닫는다                    스택을 앱이 소유한다. 앱이 살아 있으면 다시 올린다
② 새 스택을 멈춘다 (지우지 않는다)
     docker compose --project-name <프로젝트> down
   **`-v` 를 붙이지 않는다.** 붙이면 graph_data 가 사라져 돌아올 길이 없어진다
③ 이 변경 앞의 런타임 파일로 되돌린다
     desktop/runtime/compose.yml
     desktop/runtime/runtime-manifest.template.json   (schemaVersion 4 → 3)
     desktop/src/main/docker-stack.ts
     desktop/src/main/backend.ts
   커밋 단위로 revert 한다. 셋은 **같이** 가야 한다 — 하나만 되돌리면 앱이 주는
   변수와 compose 가 읽는 변수가 어긋나고, 그 어긋남은 **빈 문자열로 조용히** 지나간다
④ 앱을 연다
```

## 2. 자동으로 맞아 들어가는 것 — 손대지 않아도 된다

**포트 상태.** `docker-state.json` 의 `schemaVersion` 이 3(새) ↔ 2(옛) 로 다르다.
옛 코드는 3 을 못 읽고 **새로 뽑는다**. 옛 상태가 남아 엉뚱한 포트를 쓰는 일은 없다.

**비밀번호.** 새 코드는 키체인 id 를 `runtime.docker.graph.password` 로 옮기면서
**옛 id `runtime.docker.neo4j.password` 를 지우지 않는다**(복사다). 그래서 되돌린
앱이 옛 id 를 그대로 읽어 Neo4j 볼륨의 비밀번호와 맞는다.

> 옮기면서 지웠다면 되돌린 앱이 새 비밀번호를 뽑고, **볼륨의 비밀번호는 그대로인데
> 앱만 다른 값을 쓰게 되어** 인증만 실패했을 것이다. 증상이 "저장소가 안 뜬다" 가
> 아니라 "비밀번호가 틀렸다" 로 보인다.

## 3. 되돌린 뒤 **내용으로** 확인한다

떴는지가 아니라 **읽히는지**를 본다.

```bash
# 프로브는 두 구성 모두에서 돈다 — 서비스 id 가 엔진에 안 묶여 있다
ROBO_NEO4J_PASSWORD=<비밀번호> python3 scripts/probe_runtime.py \
    --project <프로젝트> --gateway <포트> --analyzer <포트> --pdf2bpmn <포트> \
    --bolt <포트> --graph-user neo4j --graph-name neo4j --compare-health
```

`graph capability` 가 `pass` 여야 한다. **`health` 만 보고 판단하지 않는다** — bolt
포트는 열려 있는데 database 가 없으면 조회에서야 터진다.

그리고 **교체 전에 있던 것이 이름으로 그대로 있는지** 확인한다. 건수만 세지 않는다.

## 4. 되돌릴 수 없게 되는 경우

```
docker compose down -v 를 돌렸다        graph_data 가 사라진다. Neo4j 쪽은 남는다
neo4j_data 볼륨을 지웠다                되돌릴 대상이 없다. 백업에서 복구해야 한다
```

**설계 graph 와 분석 graph 를 나눈 것은 되돌아가지 않는다.** Neo4j Community 는
database 가 하나뿐이라 둘을 나눌 수 없다 — 되돌리면 분석이 설계를 지우는 구성으로
같이 돌아간다. 그게 교체 전의 상태다.
