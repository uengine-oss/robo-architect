// GWT 생성 조건 확인 쿼리

// 1. 전체 Command 개수
MATCH (cmd:Command)
RETURN count(cmd) as total_commands;

// 2. GWT 생성 조건에 부합하는 Command 개수
// 조건: Command가 있고, Aggregate와 연결되어 있고, Event가 있는 Command
MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
WITH cmd, count(evt) as event_count
WHERE event_count > 0
RETURN count(DISTINCT cmd) as commands_with_events;

// 3. Command별 상세 정보 (GWT 생성 가능 여부)
MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
WITH cmd, agg, collect(DISTINCT evt.id) as event_ids
RETURN 
    cmd.id as command_id,
    cmd.name as command_name,
    agg.id as aggregate_id,
    agg.name as aggregate_name,
    size(event_ids) as event_count,
    CASE WHEN size(event_ids) > 0 THEN 'GWT 생성 가능' ELSE 'GWT 생성 불가 (Event 없음)' END as gwt_status
ORDER BY cmd.name;

// 4. 전체 Policy 개수
MATCH (pol:Policy)
RETURN count(pol) as total_policies;

// 5. GWT 생성 조건에 부합하는 Policy 개수
// 조건: Policy가 있고, TRIGGERS 관계로 Event가 연결되어 있는 Policy
MATCH (evt:Event)-[:TRIGGERS]->(pol:Policy)
RETURN count(DISTINCT pol) as policies_with_trigger_events;

// 6. Policy별 상세 정보 (GWT 생성 가능 여부)
MATCH (pol:Policy)
OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
OPTIONAL MATCH (cmd)-[:EMITS]->(target_evt:Event)
OPTIONAL MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd)
WITH pol, 
     collect(DISTINCT evt.id) as trigger_event_ids,
     collect(DISTINCT cmd.id) as invoke_command_ids,
     collect(DISTINCT target_evt.id) as target_event_ids,
     collect(DISTINCT agg.id) as aggregate_ids
RETURN 
    pol.id as policy_id,
    pol.name as policy_name,
    size(trigger_event_ids) as trigger_event_count,
    size(invoke_command_ids) as invoke_command_count,
    size(target_event_ids) as target_event_count,
    size(aggregate_ids) as aggregate_count,
    CASE 
        WHEN size(trigger_event_ids) = 0 THEN 'GWT 생성 불가 (Trigger Event 없음)'
        WHEN size(invoke_command_ids) = 0 THEN 'GWT 생성 가능 (Command 없지만 기본값 사용)'
        WHEN size(target_event_ids) = 0 THEN 'GWT 생성 가능 (Target Event 없지만 기본값 사용)'
        WHEN size(aggregate_ids) = 0 THEN 'GWT 생성 가능 (Aggregate 없지만 기본값 사용)'
        ELSE 'GWT 생성 가능'
    END as gwt_status
ORDER BY pol.name;

// 7. 실제 생성된 GWT 개수
MATCH (gwt:GWT)
RETURN count(gwt) as total_gwt_created;

// 8. Command별 GWT 생성 여부
MATCH (cmd:Command)
OPTIONAL MATCH (cmd)-[:HAS_GWT]->(gwt:GWT)
RETURN 
    cmd.id as command_id,
    cmd.name as command_name,
    CASE WHEN gwt IS NOT NULL THEN 'GWT 생성됨' ELSE 'GWT 미생성' END as gwt_status,
    gwt.id as gwt_id
ORDER BY cmd.name;

// 9. Policy별 GWT 생성 여부
MATCH (pol:Policy)
OPTIONAL MATCH (pol)-[:HAS_GWT]->(gwt:GWT)
RETURN 
    pol.id as policy_id,
    pol.name as policy_name,
    CASE WHEN gwt IS NOT NULL THEN 'GWT 생성됨' ELSE 'GWT 미생성' END as gwt_status,
    gwt.id as gwt_id
ORDER BY pol.name;

// 10. 요약: GWT 생성 조건 부합 vs 실제 생성
MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
OPTIONAL MATCH (cmd)-[:HAS_GWT]->(gwt_cmd:GWT)
WITH cmd, count(DISTINCT evt) as event_count, gwt_cmd
WHERE event_count > 0
WITH count(DISTINCT cmd) as eligible_commands, count(DISTINCT gwt_cmd) as created_command_gwt

MATCH (evt:Event)-[:TRIGGERS]->(pol:Policy)
OPTIONAL MATCH (pol)-[:HAS_GWT]->(gwt_pol:GWT)
WITH eligible_commands, created_command_gwt, count(DISTINCT pol) as eligible_policies, count(DISTINCT gwt_pol) as created_policy_gwt

RETURN 
    eligible_commands as 조건부합_Command개수,
    created_command_gwt as 생성된_Command_GWT개수,
    eligible_policies as 조건부합_Policy개수,
    created_policy_gwt as 생성된_Policy_GWT개수,
    eligible_commands + eligible_policies as 총_예상_GWT개수,
    created_command_gwt + created_policy_gwt as 총_생성된_GWT개수,
    (eligible_commands + eligible_policies) - (created_command_gwt + created_policy_gwt) as 누락된_GWT개수;
