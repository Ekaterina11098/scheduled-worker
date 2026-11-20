"""Read exact owner Guangzhou articles; never sends stock or notifications."""
import os,json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_storage_health import verify_runtime_storage
from stock_china_mgt import read_store,policy
ROOT='technical:owner-guangzhou21-health:2026-11-20'
ARTICLES='338-cristinebag-ebony 339-cristinebag-black 340-elodiebag-darkred 341-elodiebag-black 342-elodiebag-coffee 343-colettebag-black 344-colettebag-darkred 345-aureliebag-black 346-aureliebag-coffee 354-odettebag-black 355-odettebag-coffee 356-noemibag-black 357-noemibag-coffee 358-celestebag-green 359-celestebag-darkred 360-celestebag-coffee 361-celestebag-black 362-celineabag-black 363-celineabag-darkred 364-celineabag-coffee 365-celineabag-green'.split()
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);data={'approval':{'articles':ARTICLES,'warehouse':2373413,'cabinet':2,'allocation':'all_free_after_exact_store_unposted_orders'},'started_at':time.time(),'status':'reading'}
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(data['approval']),digest(data['approval']),'cloud-owner',data['started_at']))
   shared=SharedRequests(s,budget=lambda:g.check_run_budget());g.check_run_budget=lambda:None
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   g._CACHE_GET=lambda k:shared.get(k);g._CACHE_SET=lambda k,v,ttl:shared.put(k,v,ttl)
   g.RUN_DEADLINE=time.monotonic()+2400
   os.environ['STOCK_STORAGE_PROOF_FILE']=os.path.join(os.environ['RUNNER_TEMP'],'guangzhou21-proof.json')
   os.environ['STOCK_STORAGE_PROOF_SCOPE']=ROOT
   def hw(v):data['storage_probe']=v;save()
   def hr():
    v=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit();return v['storage_probe']
   probe={'scope':ROOT,'nonce':os.urandom(16).hex()};verify_runtime_storage(hw,hr,probe);last=[time.monotonic()]
   def budget():
    if time.monotonic()-last[0]>=120:verify_runtime_storage(hw,hr,probe);last[0]=time.monotonic()
   g.check_run_budget=budget
   try:
    import stock_guangzhou_owner21 as owner
    if set(ARTICLES)!=set(owner.ARTICLES):raise RuntimeError('Owner approval article mismatch')
    result=owner.Pool(s,owner.PARENT).publish(g)
    data.update(status='complete',execution_complete=True,publication_root=owner.ROOT,completed_at=time.time());save()
    seal('owner-guangzhou21-publication',result)
    print(json.dumps({'status':result['status'],'confirmed_articles':len(result['confirmed_articles']),'units':sum(r['target'] for r in result['preview']['rows']),'notifications':0}))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__);save();seal('owner-guangzhou21-error',error(exc));raise
