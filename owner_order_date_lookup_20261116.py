"""Read-only WB order/sale identifier lookup; request and results stay private."""
import json,time
from datetime import datetime,timedelta,timezone
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
import tg_agent_new as g
ROOT='technical:owner-order-date-lookup:2026-11-16:ooo:1'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   store=Store(db,postgres=True)
   row=store.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()
   if not row:raise RuntimeError('Private lookup request missing')
   data=json.loads(row[0]);req=data['request']
   if req['cabinet']!=0:raise RuntimeError('Only requested OOO reader allowed')
   shared=SharedRequests(store);g.STOCK_REQUEST_GATE=shared
   g.check_run_budget=lambda:None
   g._CACHE_GET=lambda key:shared.get(key)
   g._CACHE_SET=lambda key,value,ttl:shared.put(key,value,ttl)
   def save():
    with store.transaction():store.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(data),ROOT))
   try:
    data['status']='reading';data['started_at']=time.time();save()
    first=(datetime.now(timezone.utc)-timedelta(days=req['lookback_days'])).date().isoformat()
    data['from_date']=first;data.setdefault('sources',{})
    wanted=req['identifier'].casefold()
    for kind in ('orders','sales'):
     if data['sources'].get(kind,{}).get('complete'):continue
     rows=g.api('GET',g.WB_STATS+'/api/v1/supplier/'+kind,g.cabinet_tokens()[0],params={'dateFrom':first,'flag':0},retry_read_network=True)
     if not isinstance(rows,list):raise RuntimeError('Statistics response is not a list')
     if len(rows)>=80000:raise RuntimeError('Statistics row limit requires pagination')
     matches=[r for r in rows if any(str(r.get(k,'')).casefold()==wanted for k in ('srid','rid','rId','requestId'))]
     data['sources'][kind]={'complete':True,'observed_at':time.time(),'rows_scanned':len(rows),'matches':matches};save()
    data['status']='complete';data['completed_at']=time.time();save();seal('order-date-lookup',data)
    print(json.dumps({'status':'complete','order_matches':len(data['sources']['orders']['matches']),'sales_matches':len(data['sources']['sales']['matches'])}))
   except Exception as exc:
    data.update(status='stopped',error_type=type(exc).__name__,error=str(exc),retry_after=getattr(exc,'wait',0));save();seal('order-date-lookup-error',error(exc));raise
