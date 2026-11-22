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
ROOT=d.OWNER_CANCEL_RECOVERY
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit()
   data=json.loads(row[0]) if row else dict(status='reading',started=time.time(),owner_authorization=d.CANCEL_AUTHORIZATION)
   if data.get('owner_authorization')!=d.CANCEL_AUTHORIZATION:raise Stopped('Owner authorization drift')
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(d.CANCEL_AUTHORIZATION),digest(d.CANCEL_AUTHORIZATION),'owner-stock-recovery',data['started']))
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
    body=[b for seq,b,state,_ in s.operations(ROOT+':china-mgt') if state=='confirmed']
    if len(body)!=1 or body[0]['article']!=d.CANCEL_AUTHORIZATION['article'] or body[0]['target']!=2:raise Stopped('Exact single-article completion missing')
    actual=d.Pool(s,ROOT).read(g,body)
    data.update(status='complete',completed=time.time(),child=ROOT+':china-mgt',actual=actual,rows=child['preview']['rows'],released_cancellations=child['preview'].get('released_cancellations',[]))
    if actual.get(4006214639)!=2:raise Stopped('Final WB readback no longer equals two; no blind resend')
    save();seal('china-cancel-release',data);print(json.dumps(dict(status='complete',article=d.CANCEL_AUTHORIZATION['article'],actual=2)))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0));save();seal('china-cancel-release-error',error(exc));raise
