"""Read-only verification through the real scheduled source and planner; no stock writes or messages."""
import os,json,time
import tg_agent_new as g,auto_stock as a
import stock_regular_service as service
import stock_belt_common_pool as b
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped,canonical,digest
from stock_execution_fence import cloud_writer,EXPLICIT_HOLDS
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
from stock_performance import preflight
from stock_storage_health import verify_runtime_storage
ROOT='technical:owner-allocation-proposal:2026-11-24:screenshot-nine'
INPUT={"479-dominiquebag-cream":10,"64-noelbag-zchocolate":5,"401-cymebag-beige":3,"193-kaylabag-green":1,"19-furscarf-leo":1,"38-furmanizhka-white":1,"46-zont-green":3,"53-zont-ifio":8,"018-junebag-black":22}
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);data=dict(status='reading',started=time.time(),stock_writes=0,approval=dict(instruction='proposal_only',physical_msk=INPUT))
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(data['approval']),digest(data['approval']),'cloud-owner-readonly',data['started']))
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared;g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   install(g);g.STOCK_FURCOAT_ENABLED=True;g.RUN_DEADLINE=time.monotonic()+2400
   from stock_card_lifecycle import Lifecycle
   g.STOCK_CARD_LIFECYCLE=Lifecycle(g,s,shared)
   g.STOCK_CANCELLATION_STORE=s
   os.environ['STOCK_CANCELLATION_RESTORE_ENABLED']='true'
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'allocation-proposal-proof.json');os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   def hw(v):data['storage_probe']=v;save()
   def hr():
    row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit();return json.loads(row[0])['storage_probe']
   probe=dict(scope=ROOT,nonce=os.urandom(16).hex());verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   try:
    preflight(g,shared)
    source=service.capture(g)
    if source.get('orders_complete') is not True:raise Stopped('Full fresh demand data not available')
    if source.get('unposted_orders',{}).get('complete') is not True:raise Stopped('Common reserve proof missing')
    import copy,math
    from stock_unposted_source import select_ms_store
    from stock_ms_complete_report import read_store_report
    from urllib.parse import urlparse
    selected=select_ms_store(g)
    goods=g.ms_rows(g.MS_API+'/entity/assortment',filter='archived=false;archived=true')
    reports=read_store_report(g,selected,goods)
    index={urlparse(v.get('meta',{}).get('href','')).path:v for v in goods};native={}
    for row in reports:
     ref=row.get('assortment')or{};href=(ref.get('meta')or row.get('meta')or{}).get('href','')
     art=g.norm(row.get('article')or ref.get('article')or index.get(urlparse(href).path,{}).get('article'))
     if art not in INPUT:continue
     entries=[v for v in row.get('stockByStore',[]) if g.is_exact_ms_store_entry(v,selected)]
     if not entries or any(type(v.get('reserve'))not in(int,float) or v['reserve']<0 for v in entries):raise Stopped('Native MS reserve unknown: '+art)
     native[art]=native.get(art,0)+sum(v['reserve'] for v in entries)
    reserve=source['unposted_orders'];cards=service.restored_cards(source);rows=[]
    g.STOCK_BATCH_WAREHOUSES=source['warehouses']
    for art,physical in INPUT.items():
     pending=reserve['pending'].get(art,0);free=max(0,physical-pending)
     n=4 if art in (source.get('ozon')or{}).get('locations',{}) else 3
     r=dict(article=art,physical=physical,ms_physical=source['moscow_raw'].get(art),pending=pending,native=native.get(art),free=free)
     try:
      if art not in source['moscow_raw']:raise Stopped('MS identity/quantity unavailable')
      if r['native'] is None or r['native']>0:raise Stopped('Native MS reservation needs overlap reconciliation')
      if art in reserve.get('blocked',{}):raise Stopped(reserve['blocked'][art])
      if art in EXPLICIT_HOLDS or g.is_excluded_item(art):raise Stopped('Owner exclusion')
      if reserve.get('bootstrap_quarantine',{}).get(art,{}).get('legacy_upper',0)>0:raise Stopped('Historical reserve requires overlap verification')
      current=a.before_quantities(art,cards[:n],source['fbs'][:n])
      target=a.plan_article(art,free,cards[:n],source['fbs'][:n],source['sales'][:n])
      if a.active_total(target)>free:raise Stopped('Allocation exceeds free stock')
      r.update(current=current,target=target,unallocated=free-a.active_total(target),sales=[source['sales'][i][0].get(art,0) for i in range(n)])
     except Exception as exc:r.update(error=str(exc),error_type=type(exc).__name__)
     rows.append(r)
    data.update(status='complete',completed=time.time(),source_started=source['started'],rows=rows,reserve_proof=[v for v in reserve.get('proof',[]) if v['article'] in INPUT],orders_complete=True)
    save();seal('allocation-proposal',data);print(json.dumps(dict(status='complete',stock_writes=0,articles=len(rows))))

   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0));save();seal('belt-common-verification-error',error(exc));raise
