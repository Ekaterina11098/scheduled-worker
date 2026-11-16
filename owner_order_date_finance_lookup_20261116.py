"""One read-only financial detail page; exact private identifier search."""
import os,sys,json,time
from datetime import datetime,timedelta,timezone
sys.path.insert(0,'scripts')
from fbs_document_chain import Cache,Transport,stamp,now
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
import tg_agent_new as g
ROOT='technical:owner-order-date-lookup:2026-11-16:ooo:1'
ACCESS='weekly_report_review:ooo:finance_access:v1'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   store=Store(db,postgres=True);cache=Cache(Transport())
   data=json.loads(store.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);req=data['request']
   shared=SharedRequests(store);g.STOCK_REQUEST_GATE=shared;g.check_run_budget=lambda:None
   g._CACHE_GET=lambda key:shared.get(key);g._CACHE_SET=lambda key,value,ttl:shared.put(key,value,ttl)
   def save():
    with store.transaction():store.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(data),ROOT))
   try:
    if data['sources'].get('finance',{}).get('complete'):print('Existing finance lookup retained');sys.exit(0)
    access=cache.get(ACCESS) or {}
    if access.get('next_allowed_at') and stamp(access['next_allowed_at'])>datetime.now(timezone.utc):
     raise RuntimeError('Account finance cooldown active until '+access['next_allowed_at'])
    until=(datetime.now(timezone.utc)+timedelta(hours=12,seconds=5)).isoformat()
    cache.put(ACCESS,dict(access,last_request_at=now(),next_allowed_at=until,task=ROOT,status='requesting'))
    data['status']='reading_finance';save()
    token=os.environ['WB_FINANCE_TOKEN_1']
    body={'dateFrom':data['from_date'],'dateTo':datetime.now(timezone.utc).date().isoformat(),'period':'weekly','limit':100000,'rrdId':0}
    rows=g.api('POST','https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed',token,json=body,allow_redirects=False)
    if rows=={}:rows=[]
    if not isinstance(rows,list):raise RuntimeError('Financial detail response is not a list')
    wanted=req['identifier'].casefold();tail=wanted.removeprefix('i')
    matches=[r for r in rows if wanted in json.dumps(r,ensure_ascii=False).casefold() or tail in json.dumps(r,ensure_ascii=False).casefold()]
    product=[{k:r.get(k) for k in ('srid','orderUid','orderId','nmId','vendorCode','orderDt','saleDt','docTypeName','sellerOperName','reportId')} for r in rows if r.get('nmId')==req['nm_id']]
    data['sources']['finance']={'complete':len(rows)<100000,'rows_scanned':len(rows),'observed_at':time.time(),'matches':matches,'product_rows':product,'body':body}
    data['status']='complete';save();seal('order-date-finance-lookup',data)
    cache.put(ACCESS,dict(access,last_request_at=now(),next_allowed_at=until,task=ROOT,status='read_complete'))
    print(json.dumps({'status':'complete','exact_matches':len(matches),'product_rows':len(product),'rows_scanned':len(rows)}))
   except Exception as exc:
    data.update(status='finance_stopped',finance_error=str(exc));save();seal('order-date-finance-error',error(exc));raise
