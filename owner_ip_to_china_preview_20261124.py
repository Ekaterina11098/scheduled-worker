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
ROOT='technical:owner-ip-to-china-preview:2026-11-24'
INPUT={}
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);data=dict(status='reading',started=time.time(),stock_writes=0,approval=dict(instruction='owner_all_ip_fbs_to_china_preview',ip_warehouse=854652,china_warehouse=2126188))
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
    preflight(g,shared,orders=False)
    reference=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',('technical:stock-daily:2026-11-24:0700',)).fetchone();db.commit()
    if not reference:raise Stopped('Completed sales reference missing')
    sales=json.loads(reference[0])['source']['sales']
    ip_catalog=g.get_real_wb_cards_and_scores(g.cabinet_tokens()[1])
    scope={g.norm(c.get('vendorCode')) for c in ip_catalog if g.norm(c.get('vendorCode'))}
    original_fbo=g.load_cabinet_fbo
    g.load_cabinet_fbo=lambda token,cards:None
    try:source=service.capture(g,scope,sales)
    finally:g.load_cabinet_fbo=original_fbo
    source['owner_fbs_transfer_only']=True
    source['fbo_not_read_reason']='FBS transfer preserves total exposure and does not calculate demand or alter FBO'
    if source.get('orders_complete') is not True:raise Stopped('Full fresh demand data not available')
    if source.get('unposted_orders',{}).get('complete') is not True:raise Stopped('Common reserve proof missing')
    cards=service.restored_cards(source)
    rows=[];positive={art:q for art,q in source['fbs'][1].items() if type(q) in (int,float) and q>0}
    from stock_batch_transport import locations_for_article
    for art,q in sorted(positive.items()):
     row=dict(article=art,ip=q,china=source['fbs'][2].get(art),ooo=source['fbs'][0].get(art),physical=source['moscow_raw'].get(art),pending=source['unposted_orders']['pending'].get(art,0),free=source['unposted_orders']['available_moscow'].get(art),china_eligible=art in g.eligible_articles(cards[2]),ip_ids=sorted(g.article_size_ids(cards[1]).get(art,set())),china_ids=sorted(g.article_size_ids(cards[2]).get(art,set())),china_cards=[c for c in source['cards'][2] if g.norm(c.get('vendorCode'))==art],reserve_error=source['unposted_orders'].get('blocked',{}).get(art))
     rows.append(row)
    data.update(status='complete',completed=time.time(),source=source,rows=rows,ip_articles=len(rows),ip_units=sum(positive.values()))
    save();seal('ip-to-china-preview',data);print(json.dumps(dict(status='complete',stock_writes=0,ip_articles=len(rows),ip_units=sum(positive.values()))))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__,retry_after=getattr(exc,'wait',0));save();seal('ip-to-china-preview-error',error(exc));raise
