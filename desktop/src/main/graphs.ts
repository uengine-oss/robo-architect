/**
 * lite 의 그래프 이름 — 번들 Ontological DB 하나에 둘이 먼저 있다.
 *
 *   GRAPH_USER      엔진(postgres)의 역할. Bolt 게이트웨이는 Bolt 사용자를 그대로 PG 역할로
 *                   쓰므로 앱도 이 이름으로 붙는다(`neo4j` 로 붙으면 인증 실패 — 2026-10-30 실측).
 *   GRAPH_DESIGN    설치 때 만들어지는 기본 프로젝트 그래프. Bolt 세션이 database 를 안 주거나
 *                   "neo4j" 를 주면 게이트웨이가 이 그래프로 보낸다(OG_BOLT_GRAPH).
 *   GRAPH_ANALYSIS  분석기가 통째로 비우고 다시 쓰는 그래프 — 프로젝트로 고르면 안 된다.
 *
 * ⚠ 설계와 분석이 **같으면 엔진이 기동을 거절한다**(분석이 설계를 지운다).
 */
export const GRAPH_USER = "robo";
export const GRAPH_DESIGN = "robo";
export const GRAPH_ANALYSIS = "analyzer_run";
