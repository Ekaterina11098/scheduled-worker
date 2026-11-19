"""Owner-approved model-only zero; no notification or daily-slot replay."""
import os,json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest
from stock_shared_requests import SharedRequests
from stock_execution_fence import cloud_writer
from stock_storage_health import verify_runtime_storage
from stock_ip_noel_zero import ROOT,execute,saved
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);g.check_run_budget=lambda:None
   shared=SharedRequests(s,budget=lambda:g.check_run_budget())
   g.STOCK_REQUEST_GATE=shared
   g._CACHE_GET=lambda key:shared.get(key)
   g._CACHE_SET=lambda key,value,ttl:shared.put(key,value,ttl)
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'ip-noel-proof.json')
   os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   health=ROOT+':health';probe={'scope':ROOT,'nonce':os.urandom(16).hex()}
   def hw(value):
    with s.transaction():
     s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(health,canonical(value),'{}',digest({}),'stock-storage-health',time.time()))
   def hr():
    row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(health,)).fetchone();db.commit()
    return json.loads(row[0])
   verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:
     verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   original=g.api
   def guarded(method,*args,**kwargs):
    budget();return original(method,*args,**kwargs)
   g.api=guarded
   try:
    result=execute(g,s);seal('ip-noel-zero',result)
    print(json.dumps({'execution_complete':result['execution_complete'],'changed_sizes':result['changed_sizes'],'previous_units':result['previous_units'],'warehouses':len(result['warehouses'])}))
   except Exception as exc:
    with s.transaction():
     if saved(s):s.event(ROOT,None,'runner_stopped',{'type':type(exc).__name__,'message':str(exc)})
    seal('ip-noel-error',error(exc));raise
