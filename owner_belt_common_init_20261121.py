"""One owner-approved initialization: only zero quantities on four belt sizes."""
import os,json,time
import tg_agent_new as g
import stock_belt_common_pool as b
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_storage_health import verify_runtime_storage
from stock_cloud_execution import _INTENT
ROOT=b.INIT_ROOT
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);p=b.policy();raw=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit()
   data=json.loads(raw[0]) if raw else dict(approval=b.binding(),started=time.time(),status='preflight',execution_complete=False)
   if data.get('approval')!=b.binding():raise Stopped('Initialization approval mismatch')
   if data.get('execution_complete'):print('already_complete');raise SystemExit(0)
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(data['approval']),digest(data['approval']),'cloud-owner-init',data['started']))
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'belt-init-proof.json');os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   def hw(v):data['storage_probe']=v;save()
   def hr():
    v=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit();return v['storage_probe']
   probe=dict(scope=ROOT,nonce=os.urandom(16).hex());verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   def reconcile():
    pending=[(i,x,state) for i,x,state,_ in s.operations(ROOT) if state in ('sent','uncertain')]
    if not pending:return
    values=b.read(g)
    for i,x,state in pending:
     actual=values.get(x['location']['chrtId'])
     s.transition(ROOT,i,state,'confirmed' if actual==0 else 'uncertain',dict(actual=actual,readback_at=time.time()))
    if any(state in ('sent','uncertain') for _,_,state,_ in s.operations(ROOT)):raise Stopped('Zero initialization readback unknown; read only, never resend')
   try:
    reconcile();token=g.cabinet_tokens()[1]
    reply=g.api('POST',g.WB_CONTENT+'/content/v2/get/cards/list',token,json={'settings':{'cursor':{'limit':100},'filter':{'withPhoto':-1,'textSearch':str(p['nmID'])}}},retry_read_network=True)
    cards=[v for v in reply.get('cards',[]) if v.get('nmID')==p['nmID']]
    b.validate_cards(g,[[],cards,[]]);data.update(card_evidence=cards,card_observed_at=time.time())
    product=g.api('GET',g.MS_API+'/entity/product/'+p['ms_product_id'],g.MS_TOKEN,wb=False,retry_read_network=True);b.validate_goods(g,[product])
    data['ms_product_readback']={k:product.get(k) for k in ['id','article','syncId','barcodes']}
    if not s.operations(ROOT):
     before=b.read(g);data.update(destination_before={str(k):v for k,v in before.items()},status='prepared')
     with s.transaction():
      save();s.sql('INSERT INTO stock_sku_locks VALUES(?,?) ON CONFLICT(article) DO NOTHING',(b.ARTICLE,ROOT))
      if s.sql('SELECT owner_run FROM stock_sku_locks WHERE article=?',(b.ARTICLE,)).fetchone()!=(ROOT,):raise Stopped('Another writer owns this article')
      for seq,ident in enumerate(p['size_ids']):
       body=dict(article=b.ARTICLE,before=before.get(ident),target=0,initialization=ident not in before,location=dict(warehouse=p['warehouse'],chrtId=ident))
       state='confirmed' if before.get(ident)==0 else 'prepared'
       s.sql('INSERT INTO stock_operations VALUES(?,?,?,?,?)',(ROOT,seq,canonical(body),'prepared',state));s.event(ROOT,seq,state,dict(actual=before.get(ident),reason='owner common-pool zero initialization'))
    pending=[(i,x) for i,x,state,_ in s.operations(ROOT) if state=='prepared']
    if pending:
     shared.wait_ready(token,g.WB_MARKET+'/api/v3/stocks/'+str(p['warehouse']))
     with s.transaction():
      for seq,body in pending:
       if s.sql("UPDATE stock_operations SET state='sent' WHERE run=? AND seq=? AND state='prepared'",(ROOT,seq)).rowcount!=1:raise Stopped('Initialization state drift')
       if s.sql('INSERT INTO stock_events VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',(digest([ROOT,'dispatch',seq]),ROOT,seq,'dispatch_claimed',time.time(),'{}')).rowcount!=1:raise Stopped('Initialization already claimed')
     payload=[dict(chrtId=x['location']['chrtId'],amount=0) for i,x in pending]
     marker=_INTENT.set(dict(owner_belt_pool_init=ROOT,belt_store=s,belt_seqs=[i for i,x in pending],warehouse=p['warehouse'],token=token,stocks=payload,used=False))
     try:g.api('PUT',g.WB_MARKET+'/api/v3/stocks/'+str(p['warehouse']),token,json={'stocks':payload})
     except Exception:
      for i,x in pending:s.transition(ROOT,i,'sent','uncertain',dict(reason='transport result requires readback'))
      raise
     finally:_INTENT.reset(marker)
     reconcile()
    final=b.read(g)
    if set(final)!=set(p['size_ids']) or any(final.values()) or any(state!='confirmed' for _,_,state,_ in s.operations(ROOT)):raise Stopped('Explicit zero readback required for every size')
    with s.transaction():
     data.update(status='complete',execution_complete=True,completed=time.time(),final={str(k):v for k,v in final.items()});save()
     s.sql('DELETE FROM stock_sku_locks WHERE owner_run=?',(ROOT,))
    seal('belt-common-init',data);print(json.dumps(dict(status='complete',confirmed_sizes=len(final),total_fbs=0)))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__);save();seal('belt-common-init-error',error(exc));raise
