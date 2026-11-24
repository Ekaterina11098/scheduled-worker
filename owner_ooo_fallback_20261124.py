"""Execute only the owner-authorized temporary IP FBS transfer."""
import os,json,time
import tg_agent_new as g
import stock_owner_ooo_fallback as m
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
from stock_storage_health import verify_runtime_storage
from stock_performance import preflight
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);d=m.saved(s)
   if d is None:
    parent=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(m.APPROVAL['source_root'],)).fetchone()[0])
    if not parent.get('execution_complete'):raise Stopped('Completed source transfer required')
    d=dict(approval=m.APPROVAL,started=time.time(),status='authorized',budget={a:m.qty(v['units']) for a,v in parent['held'].items()},china_plan={},held={})
    with s.transaction():m.save(s,d)
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   install(g);g.STOCK_FURCOAT_ENABLED=True;g.RUN_DEADLINE=time.monotonic()+2400
   from stock_card_lifecycle import Lifecycle
   g.STOCK_CARD_LIFECYCLE=Lifecycle(g,s,shared)
   g.STOCK_CANCELLATION_STORE=s
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'all-ip-transfer-proof.json')
   os.environ['STOCK_STORAGE_PROOF_SCOPE']=m.ROOT
   probe=dict(scope=m.ROOT,nonce=os.urandom(16).hex())
   def hw(value):
    data=m.saved(s);data['storage_probe']=value
    with s.transaction():m.save(s,data)
   def hr():
    data=m.saved(s);db.commit();return data['storage_probe']
   verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   try:
    if not d.get('execution_complete'):preflight(g,shared,orders=False)
    result=m.execute(g,s);seal('all-ip-to-china-transfer',result)
    print(json.dumps({k:result.get(k) for k in ('status','execution_complete','ooo_added','unpublished_units')}))
   except Exception as exc:
    data=m.saved(s);data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0))
    with s.transaction():m.save(s,data)
    seal('all-ip-transfer-error',error(exc));raise
