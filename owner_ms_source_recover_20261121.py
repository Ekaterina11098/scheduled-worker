"""Exact owner-approved fresh recovery; preserve the original completed morning journal."""
import os,json,time
from stock_deploy_support import runtime_db,seal,error
from stock_execution_fence import cloud_writer
from stock_operation_store import Store,Stopped,canonical,digest
from stock_china_mgt_daily import OWNER_RECOVERY,OWNER_AUTHORIZATION
from stock_regular_job import send
from stock_regular_service import run
FAILED='technical:stock-daily:2026-11-21:0700'
AUTH={'authorization':OWNER_AUTHORIZATION,'failed_scope':FAILED,'instruction':'Исправь','warehouse':2373413}
try:
 with runtime_db() as lock:
  with cloud_writer(lock):
   with runtime_db() as db:
    s=Store(db,postgres=True)
    old=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(FAILED,)).fetchone()
    if not old:raise Stopped('Original morning checkpoint missing')
    old=json.loads(old[0])
    if old.get('progress',{}).get('confirmed')!=0 or any(old.get('progress',{}).get(k,0) for k in ('sent','prepared','uncertain','remaining')):raise Stopped('Original morning execution differs; reconcile before recovery')
    prior=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(OWNER_RECOVERY,)).fetchone()
    if prior:
     if json.loads(prior[0]).get('owner_authorization')!=AUTH:raise Stopped('Recovery approval conflict')
    else:
     preview=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',('technical:owner-ms-repaired-preview:2026-11-21',)).fetchone()
     if not preview or json.loads(preview[0]).get('status')!='complete':raise Stopped('Complete live source verification required before recovery')
     from stock_cooldowns import inherited_cooldowns
     data=dict(engine='group-checkpoint-v1',started=time.time(),generation=0,cache=inherited_cooldowns(s,time.time()),registry={},history_runs=[],frozen=[],status='collecting',china_mgt_required=True,owner_authorization=AUTH,original_blocked_count=len(old['full_plan']['blocked']))
     with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?)',(OWNER_RECOVERY,canonical(data),'{}',digest({}),'technical-no-executor',time.time()))
 result=run(runtime_db,send,OWNER_RECOVERY.removeprefix('technical:stock-daily:'))
 seal('owner-ms-recovery',result)
 print(json.dumps(result))
except Exception as exc:
 seal('owner-ms-recovery-error',error(exc));print(json.dumps({'status':'stopped','error_type':type(exc).__name__}));raise
