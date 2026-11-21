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
ROOT='technical:owner-belt-common-verify:2026-11-21'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);data=dict(status='reading',started=time.time(),stock_writes=0,approval=b.binding())
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(data['approval']),digest(data['approval']),'cloud-owner-readonly',data['started']))
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared;g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   install(g);g.STOCK_FURCOAT_ENABLED=True;g.RUN_DEADLINE=time.monotonic()+2400
   from stock_card_lifecycle import Lifecycle
   g.STOCK_CARD_LIFECYCLE=Lifecycle(g,s,shared)
   g.STOCK_CANCELLATION_STORE=s
   os.environ['STOCK_CANCELLATION_RESTORE_ENABLED']='true'
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'belt-common-verification-proof.json');os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
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
    proof=source.get('common_article_pool')or{}
    if any(proof.get(k)!=v for k,v in b.binding().items()):raise Stopped('Common source not attached to scheduled capture')
    if b.ARTICLE in EXPLICIT_HOLDS:raise Stopped('Legacy belt exclusion still active')
    plan=service.plan_source(g,a,source,set(EXPLICIT_HOLDS),set())
    blocked=[r for r in plan['blocked'] if r['article']==b.ARTICLE]
    if blocked:raise Stopped('Belt blocked by scheduled planner: '+str(blocked))
    reserve=source['unposted_orders'];data.update(status='complete',completed=time.time(),physical=source['moscow_raw'][b.ARTICLE],pending=reserve['pending'].get(b.ARTICLE,0),available=reserve['available_moscow'][b.ARTICLE],fbs=source['fbs'][1][b.ARTICLE],common_pool=proof,belt_operations=[v for v in plan['articles'] if v['article']==b.ARTICLE],belt_manual=[v for v in plan['manual'] if v['article']==b.ARTICLE],orders_complete=True,source_reports=source.get('ms_stock_reports'),blocked=blocked)
    save();seal('belt-common-verification',data)
    print(json.dumps(dict(status='complete',stock_writes=0,article=b.ARTICLE)))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0));save();seal('belt-common-verification-error',error(exc));raise
