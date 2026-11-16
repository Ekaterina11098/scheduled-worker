"""Read-only readiness check; never executes a stock slot or sends messages."""
import os,json,time
from datetime import datetime,timezone
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_performance import preflight
from stock_china_mgt import collect_preview,select_warehouse
from stock_china_mgt_daily import approval,validate_source
from stock_daily_entry import validate_start
ROOT='technical:guangzhou-new-readiness:2026-11-16'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);data={'started_at':time.time(),'status':'checking','stock_writes':0}
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'read-only-readiness',time.time()))
   save()
   shared=SharedRequests(s);g.STOCK_REQUEST_GATE=shared;g.check_run_budget=lambda:None
   g._CACHE_GET=lambda key:shared.get(key);g._CACHE_SET=lambda key,value,ttl:shared.put(key,value,ttl)
   original=g.api
   def readonly(method,*args,**kwargs):
    if method.upper() in ('PUT','DELETE','PATCH'):raise Stopped('Readiness cannot write business data')
    return original(method,*args,**kwargs)
   g.api=readonly
   try:
    day=validate_start(datetime(2026,11,16,17,tzinfo=timezone.utc),'true','1630')
    parent='technical:stock-daily:'+day
    data['evening_approval']=approval(parent)
    if data['evening_approval']['warehouse']!=2373413:raise Stopped('Evening warehouse mismatch')
    old=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',('technical:guangzhou-new-restore:2026-11-16',)).fetchone()
    if not old or not json.loads(old[0]).get('execution_complete'):raise Stopped('Restoration incomplete')
    locks=s.sql('SELECT article FROM stock_sku_locks WHERE article LIKE ?',('china-mgt-2308581/%',)).fetchall();db.commit()
    if locks:raise Stopped('China physical pool has outstanding locks')
    preflight(g,shared)
    data['provider_cooldowns']='ready';data['phase']='fresh_china_source';save()
    preview=collect_preview(g);rows=validate_source(preview)
    data.update(status='ready',completed_at=time.time(),warehouse=preview['warehouse'],rows=len(rows),blocked=preview['blocked'],reserved_units=preview['reserved_units'],planned_changes=sum(r['before']!=r['target'] for r in rows.values()),preview=preview)
    save();seal('guangzhou-readiness',data)
    print(json.dumps({'status':'ready','warehouse':2373413,'rows':len(rows),'blocked':len(preview['blocked']),'stock_writes':0}))
   except Exception as exc:
    data.update(status='stopped',error_type=type(exc).__name__,error=str(exc),retry_after=getattr(exc,'wait',0));save();seal('readiness-error',error(exc));raise
