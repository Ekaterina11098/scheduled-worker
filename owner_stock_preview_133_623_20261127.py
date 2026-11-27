"""Read-only fresh reservation preview against owner physical count."""
import os,time,json,math,copy
import stock_deploy_support as support,tg_agent_new as g,auto_stock as a
import stock_regular_service as service
from stock_operation_store import Store,canonical,digest,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
from stock_presence import scarcity_floor
ROOT='technical:owner-stock-preview:2026-11-27:133-623:physical2-1'
COUNTS={'133-madlenbag-green':2,'623-angelabag-brown':1}
install(g);g.STOCK_FURCOAT_ENABLED=True;g.RUN_DEADLINE=time.monotonic()+2400
api=g.api
def readonly(method,url,*args,**kw):
 if method not in ('GET','POST'):raise Stopped('Preview cannot write business data')
 if method=='POST' and 'moysklad' in url:raise Stopped('MS preview GET only')
 return api(method,url,*args,**kw)
g.api=readonly
with cloud_writer(support.runtime_db()):
 with support.runtime_db() as db:
  store=Store(db,postgres=True);shared=SharedRequests(store,budget=g.check_run_budget)
  g.STOCK_SHARED_ORDERS=shared;g.STOCK_REQUEST_GATE=shared;g._CACHE_GET=shared.get;g._CACHE_SET=shared.put
  baseline=json.loads(store.sql('SELECT snapshot FROM stock_runs WHERE id=?',('technical:stock-daily:2026-11-27:0700',)).fetchone()[0]);db.commit()
  sales=(baseline.get('manual_source') or baseline['source'])['sales']
  for attempt in range(8):
   try:source=service.capture(g,scope=set(COUNTS),sales=sales);break
   except Exception as exc:
    wait=getattr(exc,'wait',0)
    print(json.dumps({'attempt':attempt+1,'error_type':type(exc).__name__,'wait':wait}),flush=True)
    if not wait or attempt==7:raise
    remaining=math.ceil(wait)
    while remaining>0:
     part=min(30,remaining);g.check_run_budget();time.sleep(part);remaining-=part
  proof=source['unposted_orders'];cards=service.restored_cards(source);result=[]
  for art,physical in COUNTS.items():
   if art in proof.get('blocked',{}):raise Stopped('Reserve unresolved: '+art+': '+str(proof['blocked'][art]))
   msphysical=proof['physical_moscow'].get(art);available=proof['available_moscow'].get(art)
   if type(msphysical) not in (int,float) or type(available) not in (int,float):raise Stopped('Exact reserve capacity unavailable')
   reserved=max(0,math.floor(msphysical)-available)
   free=max(0,physical-reserved)
   n=4 if art in (source.get('ozon') or {}).get('locations',{}) else 3
   before=a.before_quantities(art,cards[:n],source['fbs'][:n])
   target=a.plan_article(art,free,cards[:n],source['fbs'][:n],source['sales'][:n],keep_presence=scarcity_floor(free,sum(art in g.eligible_articles(c) for c in cards[:n])))
   if target[1] not in (None,0):raise Stopped('IP FBS prohibited')
   if sum(v for v in target if v is not None)>free:raise Stopped('Preview capacity exceeded')
   result.append(dict(article=art,owner_physical=physical,ms_physical=msphysical,reserved=reserved,free=free,before=before,target=target,peak=[max(source['sales'][i][1].get(art,{}).values(),default=0) for i in range(n)],native_reserve=proof.get('native_reserves',{}).get(art),pending=proof.get('pending',{}).get(art,0)))
  data=dict(complete=True,business_writes=0,created=time.time(),owner_physical=COUNTS,rows=result,source=source,reserve_proof=proof)
  with store.transaction():store.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'owner-preview',time.time()))
  print(json.dumps({'complete':True,'rows':result,'business_writes':0}),flush=True)
