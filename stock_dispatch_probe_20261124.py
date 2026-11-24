import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db
from stock_operation_store import Store
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
from stock_live_capacity import LiveCapacity
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   data=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',('technical:stock-daily:2026-11-24',)).fetchone()[0]);db.commit()
   g.check_run_budget=lambda:None
   shared=SharedRequests(s)
   g.STOCK_SHARED_ORDERS=shared;g.STOCK_REQUEST_GATE=shared;g.STOCK_CANCELLATION_STORE=None
   install(g);g.STOCK_FURCOAT_ENABLED=True
   members=data['full_plan']['articles']
   arts={r['article'] for r in members if r.get('operations') and any(o['target']<o['before'] and o['cabinet']==members[0]['operations'][0]['cabinet'] for o in r['operations'])}
   arts=set(sorted(arts)[:10]);print(json.dumps({'scope_count':len(arts)}),flush=True)
   try:
    p=LiveCapacity(g,lambda:data['source']).proof(force=True,articles=arts)
    print(json.dumps({'fresh':True,'elapsed':time.time()-p['observed_at']}),flush=True)
   except Exception as e:
    print(json.dumps({'probe_failure':str(e),'type':type(e).__name__}),flush=True)
