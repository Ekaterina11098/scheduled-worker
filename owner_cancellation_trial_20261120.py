"""Owner-approved cancellation trial plus current manual-row audit; no Telegram sends."""
import os,json,time
from urllib.parse import urlparse
import tg_agent_new as g,auto_stock as a
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped,canonical,digest
from stock_execution_fence import cloud_writer,EXPLICIT_HOLDS
from stock_shared_requests import SharedRequests
from stock_storage_health import verify_runtime_storage
from stock_regular_service import capture,restored_cards,plan_source
from stock_prepare_members import prepare_members
from stock_group_execution import execute_groups
from stock_cancellation_credit import observe,ROOT as CANCEL_ROOT,load as cancellation_ledger
from stock_current_order_reserve import ledger_key
from stock_approved_warehouses import install
ROOT='technical:owner-cancel-trial:2026-11-20:1'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);data=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
   if data.get('execution_complete'):print(json.dumps({'status':'already_complete'}));raise SystemExit(0)
   def save():
    with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(data),ROOT))
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared;g.STOCK_CANCELLATION_STORE=s
   g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   g.STOCK_FURCOAT_ENABLED=True;install(g);g.RUN_DEADLINE=time.monotonic()+2400
   os.environ['STOCK_CANCELLATION_RESTORE_ENABLED']='false'
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'cancel-trial-proof.json')
   os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   def hw(v):data['storage_probe']=v;save()
   def hr():
    r=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit();return r['storage_probe']
   probe={'scope':ROOT,'nonce':os.urandom(16).hex()};verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   original=g.api
   def guarded(method,*args,**kw):budget();return original(method,*args,**kw)
   g.api=guarded
   try:
    old=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(data['approval']['manual_scope'],)).fetchone()[0]);db.commit()
    prior_rows=[r for p in old.get('manual_packets_v1',[]) if p.get('state')=='confirmed' for r in p.get('rows',[])]
    arts={r['article'] for r in prior_rows};data['manual_rows']=prior_rows
    if data.get('registry'):
     source=data['source'];plan=data['full_plan']
     if time.time()-source['started']>1800:raise Stopped('Saved trial source expired; reconcile sent only before fresh replan')
    else:
     data.update(status='reading',phase='fresh_capture',started=time.time());save()
     from stock_performance import preflight
     preflight(g,shared)
     source=capture(g)
     if source.get('orders_complete') is not True:raise Stopped('Complete fresh orders needed')
     reserve=source['unposted_orders']
     if reserve.get('complete') is not True:raise Stopped('Complete reservation reconciliation needed')
     raw=shared.get(ledger_key(g,source))
     if raw.get('order_catalog_complete') is not True:raise Stopped('Complete cancellation catalogue required')
     proof=observe(s,source,raw['order_catalog'],raw,arts)
     source['cancellation_credit']=proof;reserve['cancellation_credit']=proof
     data.update(source=source,cancellation_review=proof['review'],phase='native_reserves');save()
     from stock_unposted_source import select_ms_store
     msstore=select_ms_store(g)
     report=g.ms_rows(g.MS_API+'/report/stock/bystore',filter='store='+msstore['meta']['href']+';stockMode=all')
     goods=g.ms_rows(g.MS_API+'/entity/assortment',filter='archived=false;archived=true')
     index={urlparse(p.get('meta',{}).get('href','')).path:p for p in goods};native={}
     for row in report:
      ref=row.get('assortment')or{};href=(ref.get('meta')or row.get('meta')or{}).get('href','')
      art=g.norm(row.get('article')or ref.get('article')or index.get(urlparse(href).path,{}).get('article'))
      if art not in arts:continue
      entries=[v for v in row.get('stockByStore',[]) if g.is_exact_ms_store_entry(v,msstore)]
      if not entries or any(type(v.get('reserve'))not in(int,float) or v['reserve']<0 for v in entries):native[art]=None
      elif native.get(art,0) is not None:native[art]=native.get(art,0)+sum(v['reserve'] for v in entries)
     blocked=set(EXPLICIT_HOLDS)|{a for a,q in native.items() if q is None or q>0}|(arts-set(native))
     blocked|={row[0] for row in s.sql('SELECT article FROM stock_sku_locks').fetchall()};db.commit()
     full=plan_source(g,a,source,blocked,set(),credit_scope=ROOT)
     plan=dict(full,articles=[m for m in full['articles'] if m['article'] in arts and m.get('cancellation_credit')])
     plan.update(total_operations=sum(len(m['operations']) for m in plan['articles']),total_articles=len(plan['articles']))
     review=[]
     for r in prior_rows:
      art=r['article'];cab=r['cabinet'];n=4 if art in (source.get('ozon')or{}).get('locations',{}) else 3
      before=a.before_quantities(art,restored_cards(source)[:n],source['fbs'][:n]);records=[v for v in proof['review'] if v['article']==art]
      selected=[m for m in plan['articles'] if m['article']==art]
      review.append(dict(article=art,cabinet=cab,manual_before=r['before'],manual_target=r['target'],current=before,physical=reserve['physical_moscow'].get(art),pending=reserve['pending'].get(art,0),free=reserve['available_moscow'].get(art),native_reserve=native.get(art),cancelled_orders=records,automatic_target=selected[0]['target'] if selected else None,blocked=[v for v in full['blocked'] if v['article']==art]))
     data.update(full_plan=plan,review=review,native_reserves=native,registry={},status='planned',phase='plan_saved');save()
     prepare_members(s,g,plan,source,source['started'],restored_cards(source),'owner-cancellation-trial',data['registry'],ROOT)
     save()
    os.environ['STOCK_CANCELLATION_RESTORE_ENABLED']='true'
    from stock_live_capacity import LiveCapacity
    live=LiveCapacity(g,lambda:source)
    g.STOCK_CAPACITY_BEFORE_DISPATCH=lambda store,items:live.guard(store,items)
    def progress():data['phase']='executing';save()
    held=execute_groups(s,g,data['registry'],{m['article']:m for m in plan['articles']},progress)
    if held:raise Stopped('Unknown trial result; readback only, no resend')
    data.update(execution_complete=True,status='complete',phase='complete',completed=time.time(),restored=[{'article':m['article'],'before':m['before'],'target':m['target'],'cancelled_orders':m['cancellation_credit']['keys']} for m in plan['articles']]);save()
    seal('cancellation-trial',data)
    print(json.dumps({'status':'complete','reviewed_rows':len(data['review']),'restored_models':len(data['restored']),'notifications':0}))
   except Exception as exc:
    data.update(status='stopped',error_type=type(exc).__name__,error=str(exc),retry_after=getattr(exc,'wait',0));save();seal('cancel-trial-error',error(exc));raise
