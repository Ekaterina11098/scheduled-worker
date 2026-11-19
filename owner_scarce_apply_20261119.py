"""Execute only the explicit approved table; no daily slot or notification replay."""
import os,json,time
from urllib.parse import urlparse
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_storage_health import verify_runtime_storage
from stock_approved_warehouses import install
from stock_performance import preflight
from stock_owner_table_apply import execute,ROOT,saved,save
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);g.check_run_budget=lambda:None
   shared=SharedRequests(s,budget=lambda:g.check_run_budget())
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   g._CACHE_GET=lambda key:shared.get(key);g._CACHE_SET=lambda key,value,ttl:shared.put(key,value,ttl)
   g.STOCK_FURCOAT_ENABLED=True;install(g)
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'owner-table-proof.json')
   os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   probe={'scope':ROOT,'nonce':os.urandom(16).hex()}
   def hw(value):
    d=saved(s);d['storage_probe']=value
    with s.transaction():save(s,d)
   def hr():
    d=saved(s);db.commit();return d['storage_probe']
   verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:
     verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   original=g.api
   def guarded(method,*args,**kwargs):
    budget();return original(method,*args,**kwargs)
   g.api=guarded
   cache={}
   def native_read(g,articles):
    from stock_unposted_source import select_ms_store
    store=select_ms_store(g);observed=time.time()
    rows=g.ms_rows(g.MS_API+'/report/stock/bystore',filter='store='+store['meta']['href']+';stockMode=all')
    if 'products' not in cache:
     goods=g.ms_rows(g.MS_API+'/entity/assortment',filter='archived=false;archived=true')
     cache['products']={urlparse(p.get('meta',{}).get('href','')).path:p for p in goods}
    values={}
    for row in rows:
     ref=row.get('assortment')or{};href=(ref.get('meta')or row.get('meta')or{}).get('href','')
     art=g.norm(row.get('article')or ref.get('article')or cache['products'].get(urlparse(href).path,{}).get('article'))
     if art not in articles:continue
     entries=[v for v in row.get('stockByStore',[]) if g.is_exact_ms_store_entry(v,store)]
     if not entries or any(type(v.get('reserve'))not in(int,float) or v['reserve']<0 for v in entries):raise Stopped('Native reserve unknown')
     values[art]=values.get(art,0)+sum(v['reserve'] for v in entries)
    if set(values)!=set(articles):raise Stopped('Native reserve coverage incomplete')
    return values,observed
   try:
    if not saved(s).get('execution_complete'):preflight(g,shared,orders=False)
    result=execute(g,s,native_read);seal('owner-table-applied',result)
    print(json.dumps({'execution_complete':result['execution_complete'],'changed_operations':result.get('changed_operations'),'final_units':result.get('final_units')}))
   except Exception as exc:
    d=saved(s);d.update(status='stopped',last_error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0))
    with s.transaction():save(s,d)
    seal('owner-table-error',error(exc));raise
