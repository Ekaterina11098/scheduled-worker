"""Exact owner table, durable claims and fresh reserve guard. Never writes IP FBS."""
import os,time,json,math
import stock_deploy_support as support,tg_agent_new as g
import stock_regular_service as service
from stock_live_capacity import refresh_manual_source,fresh,LiveCapacity
from stock_operation_store import Store,canonical,digest,Stopped
from stock_execution_fence import cloud_writer,require_cloud_lease,require_article_allowed
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
from stock_cloud_execution import _INTENT,seller_scope
from stock_storage_health import verify_runtime_storage,require_ready
ROOT='technical:owner-apply:2026-11-27:133-623:table-1'
PREVIEW='technical:owner-stock-preview:2026-11-27:133-623:physical2-1'
TARGETS={'133-madlenbag-green':[1,0,1],'623-angelabag-brown':[0,0,1]}
WAREHOUSES=[1863255,854652,2126188]
_original_capacity_proof=LiveCapacity.proof
def owner_scoped_proof(self,force=False,articles=None):
 return _original_capacity_proof(self,force=force,articles=set(TARGETS) if articles is None else articles)
LiveCapacity.proof=owner_scoped_proof
APPROVAL=dict(date='2026-11-27',targets=TARGETS,warehouses=WAREHOUSES,ip_stock_writes=False,authorization='owner-approved-proposed-table')
install(g);g.STOCK_FURCOAT_ENABLED=True;g.RUN_DEADLINE=time.monotonic()+2400
os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'owner-two-stock-proof.json')
os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
with cloud_writer(support.runtime_db()):
 with support.runtime_db() as db:
  s=Store(db,postgres=True);shared=SharedRequests(s,budget=g.check_run_budget)
  g.STOCK_SHARED_ORDERS=shared;g.STOCK_REQUEST_GATE=shared;g._CACHE_GET=shared.get;g._CACHE_SET=shared.put
  original_budget=g.check_run_budget;last=[0]
  key=ROOT+':storage'
  def probe_write(v):
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(key,canonical(v),'{}',digest({}),'technical-no-executor',time.time()))
  def probe_read():
   row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(key,)).fetchone();db.commit();return json.loads(row[0])
  def budget():
   original_budget()
   if time.monotonic()-last[0]>=120:
    verify_runtime_storage(probe_write,probe_read,dict(scope=ROOT,nonce=os.urandom(16).hex()));last[0]=time.monotonic()
  g.check_run_budget=budget;budget()
  base=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(PREVIEW,)).fetchone()[0]);db.commit()
  source=base['source'];fact=[None];locations={}
  def read(art,cab):
   loc=locations[art][cab];values=g.get_real_wb_stocks(g.cabinet_tokens()[cab],[loc['chrtId']],loc['warehouse'])
   value=values.get(loc['chrtId'])
   if type(value) is not int or value<0:raise Stopped('Exact owner FBS unknown: '+art)
   return value
  def all_actual():return {art:[read(art,i) for i in range(3)] for art in TARGETS}
  def refresh():
   global source
   source,proof=refresh_manual_source(g,service,source,set(TARGETS))
   cards=service.restored_cards(source)
   for art in TARGETS:
    require_article_allowed(art);locs=[]
    for i in range(3):
     ids=g.article_size_ids(cards[i]).get(art,set())
     if len(ids)!=1 or source['warehouses'][i]!=[WAREHOUSES[i]]:raise Stopped('Exact owner location changed')
     if i in (0,2) and art not in g.eligible_articles(cards[i]):raise Stopped('Owner card is not eligible')
     locs.append(dict(warehouse=WAREHOUSES[i],chrtId=next(iter(ids))))
    if art in locations and locations[art]!=locs:raise Stopped('Owner size identity changed')
    locations[art]=locs
   fact[0]=dict(proof=proof,source=source,at=time.time());return fact[0]
  def validate():
   require_cloud_lease();require_ready();p=fact[0]['proof']
   if not fresh(p) or p.get('store_id')!='3c67619d-f25d-11ee-0a80-0c6f000a027a':raise Stopped('Fresh exact MSK reserve proof required')
   caps={}
   for art,target in TARGETS.items():
    if art in p.get('blocked',{}):raise Stopped('Unresolved owner reservation: '+art)
    physical=p['physical_moscow'].get(art);available=p['available_moscow'].get(art);pending=p.get('pending',{}).get(art,0);native=p.get('native_reserves',{}).get(art)
    if any(type(v) not in (int,float) for v in (physical,available,pending,native)):raise Stopped('Complete reserve quantities required')
    cap=min(available,max(0,physical-pending-native))
    oz=(fact[0]['source'].get('ozon') or {}).get('stocks',{}).get(art,0)
    if oz is None or sum(target)+oz>cap:raise Stopped('Owner table exceeds current free stock: '+art)
    if target[1]!=0:raise Stopped('IP FBS prohibited')
    caps[art]=dict(physical=physical,available=available,pending=pending,native=native,capacity=cap)
   return caps
  def load():
   row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit();return json.loads(row[0]) if row else None
  def save(root):
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(root),canonical(APPROVAL),digest(APPROVAL),'cloud-owner-fixed',root['started_at']))
  def reconcile():
   for seq,b,state,_ in s.operations(ROOT):
    if state not in ('sent','uncertain'):continue
    for delay in (0,5,15,30):
     if delay:budget();time.sleep(delay)
     actual=read(b['article'],b['cabinet'])
     if actual==b['target']:
      if not s.transition(ROOT,seq,state,'confirmed',dict(actual=actual,reconciled=True)):raise Stopped('Concurrent readback')
      break
    else:
     s.transition(ROOT,seq,state,'uncertain',dict(actual=actual,no_resend=True));raise Stopped('Owner stock waiting for WB readback; no resend')
  def main():
   root=load()
   if root and (root.get('approval')!=APPROVAL or root.get('seller_scope')!=seller_scope(g)):raise Stopped('Owner saved approval changed')
   if root and root.get('execution_complete'):return root
   refresh();caps=validate()
   if root:
    if root['locations']!={a:{str(i):v for i,v in enumerate(locations[a])} for a in locations}:raise Stopped('Saved location drift')
    reconcile()
   else:
    backup=all_actual()
    if any(v[1]!=0 for v in backup.values()):raise Stopped('IP must be zero; no IP write')
    root=dict(approval=APPROVAL,seller_scope=seller_scope(g),started_at=time.time(),status='prepared',execution_complete=False,backup=backup,backup_digest=digest(backup),locations={a:{str(i):v for i,v in enumerate(locations[a])} for a in locations},facts=caps)
    with s.transaction():
     s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?)',(ROOT,canonical(root),canonical(APPROVAL),digest(APPROVAL),'cloud-owner-fixed',root['started_at']))
     seq=0
     for art,target in TARGETS.items():
      s.sql('INSERT INTO stock_sku_locks VALUES(?,?) ON CONFLICT(article) DO NOTHING',(art,ROOT))
      if s.sql('SELECT owner_run FROM stock_sku_locks WHERE article=?',(art,)).fetchone()!=(ROOT,):raise Stopped('Earlier stock operation owns '+art)
      for cab in (0,2):
       if backup[art][cab]==target[cab]:continue
       body=dict(article=art,cabinet=cab,before=backup[art][cab],target=target[cab],location=locations[art][cab])
       s.sql('INSERT INTO stock_operations VALUES(?,?,?,?,?)',(ROOT,seq,canonical(body),'prepared','prepared'));s.event(ROOT,seq,'prepared',dict(owner_approval=digest(APPROVAL)));seq+=1
   for seq,b,state,_ in s.operations(ROOT):
    if state=='confirmed':continue
    if state!='prepared' or b['cabinet'] not in (0,2) or b['target']!=TARGETS[b['article']][b['cabinet']]:raise Stopped('Owner operation scope mismatch')
    token=g.cabinet_tokens()[b['cabinet']];url=g.WB_MARKET+'/api/v3/stocks/'+str(b['location']['warehouse'])
    shared.wait_ready(token,url)
    if not fresh(fact[0]['proof']):refresh()
    caps=validate();actual=all_actual()
    expected={a:list(v) for a,v in root['backup'].items()}
    for prev,body,status,_ in s.operations(ROOT):
     if status=='confirmed':expected[body['article']][body['cabinet']]=body['target']
    if actual!=expected:raise Stopped('Actual FBS changed before unsent owner operation')
    validate()
    with s.transaction():
     s.event(ROOT,seq,'capacity_verified',dict(facts=caps,proof_digest=fact[0]['proof']['digest'],orders_observed_at=fact[0]['proof']['observed_at'],physical_observed_at=fact[0]['proof']['physical_observed_at']))
     if s.sql("UPDATE stock_operations SET state='sent' WHERE run=? AND seq=? AND state='prepared'",(ROOT,seq)).rowcount!=1:raise Stopped('Concurrent owner dispatch')
     if s.sql('INSERT INTO stock_events VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',(digest([ROOT,'dispatch',seq]),ROOT,seq,'dispatch_claimed',time.time(),'{}')).rowcount!=1:raise Stopped('Owner operation already claimed')
    payload=[dict(chrtId=b['location']['chrtId'],amount=b['target'])]
    marker=_INTENT.set(dict(token=token,warehouse=b['location']['warehouse'],stocks=payload,used=False))
    try:g.api('PUT',url,token,json=dict(stocks=payload))
    except Exception:
     s.transition(ROOT,seq,'sent','uncertain',dict(reason='Unknown transport result; no resend'));raise
    finally:_INTENT.reset(marker)
    reconcile()
   final=all_actual()
   if final!=TARGETS or any(state!='confirmed' for _,_,state,_ in s.operations(ROOT)):raise Stopped('Exact table readback not confirmed')
   root.update(status='complete',execution_complete=True,completed_at=time.time(),final_fbs=final,final_reserve_facts=caps);save(root)
   with s.transaction():s.sql('DELETE FROM stock_sku_locks WHERE owner_run=?',(ROOT,))
   return root
  for attempt in range(8):
   try:
    root=main();print(json.dumps(dict(status=root['status'],complete=root['execution_complete'],final_fbs=root['final_fbs'],ip_stock_writes=0)),flush=True);break
   except Exception as exc:
    wait=getattr(exc,'wait',0);readback='waiting for WB readback' in str(exc)
    fresh_retry='Fresh capacity reconciliation exceeded120seconds' in str(exc)
    print(json.dumps(dict(attempt=attempt+1,error_type=type(exc).__name__,error=str(exc),wait=wait)),flush=True)
    if attempt==7 or not (wait or readback or fresh_retry):raise
    remaining=max(30,math.ceil(wait))
    while remaining>0:
     part=min(30,remaining);budget();time.sleep(part);remaining-=part
