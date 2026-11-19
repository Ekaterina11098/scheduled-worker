"""Read-only owner stock proposal; operational inputs/results remain private."""
import os,json,time,math
from urllib.parse import urlparse
import tg_agent_new as g
import auto_stock as a
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_storage_health import verify_runtime_storage
from stock_regular_service import capture,restored_cards
from stock_approved_warehouses import install
from stock_performance import preflight
ROOT='technical:owner-scarce-preview:2026-11-19:1'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   data=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
   def save():
    with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(data),ROOT))
   data.update(status='reading',started_at=time.time(),stock_writes=0);save()
   shared=SharedRequests(s);g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   g.check_run_budget=lambda:None;g.STOCK_FURCOAT_ENABLED=True;install(g)
   original=g.api
   def readonly(method,*args,**kw):
    if method.upper() in ('PUT','PATCH','DELETE'):raise Stopped('Read-only proposal cannot write business data')
    return original(method,*args,**kw)
   g.api=readonly
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'owner-preview-proof.json')
   os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   def hw(v):data['storage_probe']=v;save()
   def hr():
    r=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit();return r['storage_probe']
   verify_runtime_storage(hw,hr,{'scope':ROOT,'nonce':os.urandom(16).hex()})
   try:
    preflight(g,shared)
    data['phase']='fresh_all_cabinet_capture';save()
    source=capture(g)
    if source.get('orders_complete') is not True:raise Stopped('Complete demand required')
    reserve=source['unposted_orders']
    if reserve.get('complete') is not True:raise Stopped('Complete reserve reconciliation required')
    data['phase']='native_ms_reserves';save()
    from stock_unposted_source import select_ms_store
    store=select_ms_store(g)
    report=g.ms_rows(g.MS_API+'/report/stock/bystore',filter='store='+store['meta']['href']+';stockMode=all')
    goods=g.ms_rows(g.MS_API+'/entity/assortment',filter='archived=false;archived=true')
    index={urlparse(p.get('meta',{}).get('href','')).path:p for p in goods}
    native={};native_rows=[]
    for row in report:
     ref=row.get('assortment') or {};href=(ref.get('meta')or row.get('meta')or{}).get('href','')
     art=g.norm(row.get('article') or ref.get('article') or index.get(urlparse(href).path,{}).get('article'))
     if art not in data['inputs']:continue
     entries=[v for v in row.get('stockByStore',[]) if g.is_exact_ms_store_entry(v,store)]
     native_rows.append({'article':art,'entries':entries})
     if not entries or any(type(v.get('reserve')) not in (int,float) for v in entries):native[art]=None
     elif native.get(art,0) is not None:native[art]=native.get(art,0)+sum(v['reserve'] for v in entries)
    cards=restored_cards(source);working=set((source.get('ozon')or{}).get('locations',{}))
    from stock_ozon_scope import load_scope
    from stock_ozon_source import article as oz_article,mapping as oz_mapping
    paused={oz_article(v,oz_mapping()) for v in load_scope().get('replenishment_paused',{})}
    results=[]
    for art,physical in data['inputs'].items():
     n=4 if art in working else 3
     r={'article':art,'physical_owner':physical,'physical_api':reserve['physical_moscow'].get(art),'pending':reserve['pending'].get(art,0),'native_reserve':native.get(art),'by_cabinet':reserve.get('by_cabinet',{}).get(art),'quarantine':reserve.get('bootstrap_quarantine',{}).get(art),'reserved_groups':[p for p in reserve['proof'] if p.get('article')==art],'demand_daily':[source['sales'][i][1].get(art,{}) for i in range(n)]}
     try:
      r['before']=a.before_quantities(art,cards[:n],source['fbs'][:n])
      r['fbo']=[sum(c.get('_fbo_quantity',0) for c in cards[i] if g.norm(c.get('vendorCode'))==art) for i in range(n)]
      r['eligible']=[art in g.eligible_articles(c) for c in cards[:n]]
      if art in reserve.get('blocked',{}):raise Stopped(reserve['blocked'][art])
      if native.get(art) is None:raise Stopped('Native MS reserve unknown')
      if native[art]>0:raise Stopped('Native MS reserves require exact overlap reconciliation before final recommendation')
      free=max(0,physical-r['pending']);r['free']=free
      target=a.plan_article(art,free,cards[:n],source['fbs'][:n],source['sales'][:n])
      if n==4 and art in paused and target[3] is not None:target[3]=min(target[3],r['before'][3]);r['ozon_replenishment_paused']=True
      if a.active_total(target)>free:raise Stopped('Proposal exceeds free physical units')
      r['target']=target;r['status']='ready'
     except Exception as exc:r.update(status='blocked',reason=str(exc))
     results.append(r)
    data.update(status='complete',completed_at=time.time(),source_observed_at=source['started'],reserve_observed_at=reserve['observed_at'],physical_observed_at=reserve['physical_observed_at'],rows=results,native_rows=native_rows,reserve_proof_digest=reserve['digest'])
    save();seal('owner-scarce-preview',data)
    print(json.dumps({'status':'complete','rows':len(results),'stock_writes':0,'blocked':sum(r['status']=='blocked' for r in results)}))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0));save();seal('owner-preview-error',error(exc));raise
