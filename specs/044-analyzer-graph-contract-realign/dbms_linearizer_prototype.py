"""dbms 구문트리 → framework 모양(flat 룰 + guard/branch/next) 선형화기 시제품.
test DB 실프로시저로 출력 검증용 (라이브 코드 미투입)."""
import re
from pathlib import Path
from neo4j import GraphDatabase
env={}
for line in Path(r"d:/work/robo/project/robo-data-analyzer/.env").read_text(encoding="utf-8",errors="ignore").splitlines():
    m=re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$",line)
    if m: env[m.group(1)]=m.group(2).strip().strip('"').strip("'")
drv=GraphDatabase.driver(env.get("ROBO_NEO4J_URI"),auth=(env.get("ROBO_NEO4J_USER"),env.get("ROBO_NEO4J_PASSWORD")))

ROUTINE={"FUNCTION","PROCEDURE","METHOD","TRIGGER"}
COND={"IF","ELSIF","ELSE","LOOP","CASE","WHEN","WHILE","FOR","EXCEPTION","TRY"}  # 조건/제어 = 자식 guard 후보

def q(c,**kw):
    with drv.session(database="test") as s: return [r.data() for r in s.run(c,**kw)]

def linearize(proc_name):
    # 1. 프로시저 서브트리 전 노드 + 부모 + 룰
    rows=q("""
      MATCH (root) WHERE root.name=$n AND (root:PROCEDURE OR root:FUNCTION OR root:TRIGGER)
      MATCH (root)-[:PARENT_OF*0..]->(o)
      OPTIONAL MATCH (o)<-[:PARENT_OF]-(p)
      OPTIONAL MATCH (o)-[hr:HAS_RULE]->(rule:RULE)
      RETURN elementId(o) AS nid, labels(o)[0] AS lbl, o.start_line AS line,
             elementId(p) AS pid,
             collect(CASE WHEN rule IS NULL THEN null ELSE {lid:hr.local_rule_id, flow:hr.flow_id, stmt:rule.statement, rid:rule.id} END) AS rules
    """, n=proc_name)
    node={r['nid']:r for r in rows}
    # 2. 실행순서 = start_line 정렬(≈ preorder 실행순)
    ordered=sorted(rows, key=lambda r:(r['line'] or 0))
    # 3. 각 노드의 '대표 룰 local 시퀀스' 부여 + nearest-ancestor-with-rule(guard 후보)
    def has_rule(r): return any(x for x in r['rules'] if x)
    out=[]
    seq=0
    nid_to_pseq={}  # node -> 그 노드 첫 룰의 시퀀스(자식 guard 참조용)
    for r in ordered:
        rs=[x for x in r['rules'] if x]
        if not rs: continue
        # nearest ancestor node(트리 위로)로 guard 후보 = 조건/제어 조상의 룰
        guard=None
        cur=node.get(r['pid'])
        while cur is not None:
            if cur['nid'] in nid_to_pseq and cur['lbl'] in COND:
                guard=nid_to_pseq[cur['nid']]; break
            cur=node.get(cur['pid'])
        # 분기(else-leg): 이 노드가 ELSIF/ELSE 면 부모 아래 직전 IF/ELSIF 룰
        for x in sorted(rs, key=lambda z:(z['flow'] or '')):
            seq+=1
            lid=f"P{seq}"
            if r['nid'] not in nid_to_pseq: nid_to_pseq[r['nid']]=lid
            out.append({'lid':lid,'node_line':r['line'],'lbl':r['lbl'],'guard':guard,
                        'branch': r['lbl'] in ('ELSIF','ELSE'),
                        'stmt':(x['stmt'] or '')[:42],'orig':x['lid'],'flow':x['flow']})
    return out

for proc in ["TRG_INS_RDITAG_TB","PRC_INSERT_RDD01DD_TB2","PRC_DATA_ANALYSYS_TEST2"]:
    print(f"\n############## {proc} (선형화 결과) ##############")
    res=linearize(proc)
    print(f"  총 {len(res)} 룰")
    for x in res:
        g=f" guard={x['guard']}" if x['guard'] else ""
        b=" [branch]" if x['branch'] else ""
        print(f"  {x['lid']:4} ({x['lbl']:10} L{x['node_line']}) orig={x['orig']}{g}{b}  {x['stmt']}")
drv.close()
