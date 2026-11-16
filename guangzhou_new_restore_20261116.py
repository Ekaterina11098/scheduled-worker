"""Single owner-approved Guangzhou restore; live backup remains in private journal."""
import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store
from stock_shared_requests import SharedRequests
from stock_execution_fence import cloud_writer
from stock_guangzhou_owner_restore import execute,ROOT,saved
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   store=Store(db,postgres=True)
   shared=SharedRequests(store)
   g.STOCK_REQUEST_GATE=shared
   g.check_run_budget=lambda:None
   g._CACHE_GET=lambda k:None
   g._CACHE_SET=lambda *a:None
   try:
    result=execute(g,store)
    seal('guangzhou-owner-restore',result)
    print(json.dumps(dict(execution_complete=result['execution_complete'],restored_sizes=result['restored_sizes'],restored_units=result['restored_units'],warehouse=2373413,journal=ROOT)))
   except Exception as exc:
    info=error(exc)
    with store.transaction():
     if saved(store):store.event(ROOT,None,'runner_stopped',info)
    seal('guangzhou-owner-zero-error',info)
    print(json.dumps({'execution_complete':False,'error_type':type(exc).__name__,'message':str(exc)}))
    raise
