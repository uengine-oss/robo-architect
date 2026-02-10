// GWT 생성 조건 요약 쿼리 (한 번에 실행)

// Command와 Policy의 GWT 생성 조건 부합 여부 및 실제 생성 상태 확인
MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
OPTIONAL MATCH (cmd)-[:HAS_GWT]->(gwt_cmd:GWT)
WITH cmd, count(DISTINCT evt) as event_count, gwt_cmd
WHERE event_count > 0
WITH count(DISTINCT cmd) as eligible_commands, 
     count(DISTINCT gwt_cmd) as created_command_gwt

MATCH (evt:Event)-[:TRIGGERS]->(pol:Policy)
OPTIONAL MATCH (pol)-[:HAS_GWT]->(gwt_pol:GWT)
WITH eligible_commands, 
     created_command_gwt, 
     count(DISTINCT pol) as eligible_policies, 
     count(DISTINCT gwt_pol) as created_policy_gwt

RETURN 
    eligible_commands as `조건부합_Command개수`,
    created_command_gwt as `생성된_Command_GWT개수`,
    eligible_policies as `조건부합_Policy개수`,
    created_policy_gwt as `생성된_Policy_GWT개수`,
    eligible_commands + eligible_policies as `총_예상_GWT개수`,
    created_command_gwt + created_policy_gwt as `총_생성된_GWT개수`,
    (eligible_commands + eligible_policies) - (created_command_gwt + created_policy_gwt) as `누락된_GWT개수`;
