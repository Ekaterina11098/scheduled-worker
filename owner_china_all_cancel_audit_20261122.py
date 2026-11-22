"""Exact owner-authorized Guangzhou cancellation recovery; standard durable writer."""
import os,json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
from stock_performance import preflight
from stock_storage_health import verify_runtime_storage
import stock_china_mgt_daily as d
ROOT=d.OWNER_CANCEL_AUDIT
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit()
   data=json.loads(row[0]) if row else dict(status='reading',started=time.time(),owner_authorization=d.AUDIT_AUTHORIZATION)
   if data.get('owner_authorization')!=d.AUDIT_AUTHORIZATION:raise Stopped('Owner authorization drift')
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(d.AUDIT_AUTHORIZATION),digest(d.AUDIT_AUTHORIZATION),'owner-stock-recovery',data['started']))
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   install(g);g.STOCK_FURCOAT_ENABLED=True;g.RUN_DEADLINE=time.monotonic()+2400
   from stock_card_lifecycle import Lifecycle
   g.STOCK_CARD_LIFECYCLE=Lifecycle(g,s,shared)
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'china-cancel-proof.json');os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   def hw(v):data['storage_probe']=v;save()
   def hr():
    row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit();return json.loads(row[0])['storage_probe']
   probe=dict(scope=ROOT,nonce=os.urandom(16).hex());verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   try:
    preflight(g,shared)
    child=d.Pool(s,ROOT).publish(g)
    if not child.get('execution_complete'):raise Stopped('Recovery not fully confirmed')
    operations=s.operations(ROOT+':china-mgt')
    if any(state!='confirmed' for seq,b,state,_ in operations):raise Stopped('Audit operations not all confirmed')
    bodies=[b for seq,b,state,_ in operations]
    audit=child['preview'].get('audit_rows',[])
    actual=d.Pool(s,ROOT).read(g,audit) if audit else {}
    restored=[dict(article=b['article'],before=b['before'],target=b['target'],added=b['target']-b['before'],actual=actual.get(b['location']['chrtId'])) for b in bodies]
    data.update(status='complete_with_holds' if child.get('held_articles') else 'complete',completed=time.time(),child=ROOT+':china-mgt',actual=actual,restored=restored,audit_rows=audit,checked_articles=len(audit),released_cancellations=child['preview'].get('released_cancellations',[]),held_articles=child.get('held_articles',[]),reserve_proof=child['preview'].get('reserve_proof',[]),order_units=child['preview'].get('order_units'))
    save()
    if any(r['actual']!=r['target'] for r in restored):raise Stopped('Final WB readback changed after confirmed restoration; no blind resend')
    seal('china-all-cancel-audit',data);print(json.dumps(dict(status=data['status'],checked_articles=len(audit),restored_articles=len(restored),restored_units=sum(r['added'] for r in restored))))

   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0));save();seal('china-cancel-release-error',error(exc));raise
