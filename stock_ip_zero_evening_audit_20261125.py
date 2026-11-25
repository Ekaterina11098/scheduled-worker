import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
ROOT='technical:stock-daily:2026-11-25'
AUDIT='technical:ip-fbs-zero-final-audit:2026-11-25:evening'
with runtime_db() as preliminary:
 root_row=preliminary.execute('SELECT snapshot FROM stock_execution.stock_runs WHERE id=%s',(ROOT,)).fetchone()
 ready=json.loads(root_row[0]).get('execution_complete') is True if root_row else False
 if not ready:
  print('Stock execution remains active; final audit waits for completion',flush=True);raise SystemExit(0)
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   d=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
   if d.get('execution_complete') is not True:
    print('Evening execution still active; audit waits for completed stock run',flush=True);raise SystemExit(0)
   existing=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(AUDIT,)).fetchone();db.commit()
   if existing and json.loads(existing[0]).get('all_zero') is True:
    print('Final zero audit already confirmed',flush=True);raise SystemExit(0)
   g.check_run_budget=lambda:None
   shared=SharedRequests(s);g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared
   cards=g.get_real_wb_cards_and_scores(g.cabinet_tokens()[1])
   ids=sorted({v for values in g.article_size_ids(cards).values() for v in values})
   if not ids:raise RuntimeError('Complete IP card catalogue required')
   values={}
   for offset in range(0,len(ids),1000):
    batch=ids[offset:offset+1000]
    rows=g.api('POST',g.WB_MARKET+'/api/v3/stocks/854652',g.cabinet_tokens()[1],json={'chrtIds':batch},retry_read_network=True).get('stocks')
    if not isinstance(rows,list):raise RuntimeError('IP readback unavailable')
    for row in rows:
     ident=row.get('chrtId');q=row.get('amount')
     if ident not in batch or ident in values or type(q) is not int or q<0:raise RuntimeError('Explicit numeric IP stock required')
     values[ident]=q
   missing=sorted(set(ids)-set(values));positive={str(k):v for k,v in values.items() if v>0}
   result=dict(warehouse=854652,catalogue_sizes=len(ids),checked_sizes=len(values),unknown_sizes=missing,positive=positive,total=sum(values.values()),verified_at=time.time(),all_zero=not missing and not positive)
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(AUDIT,canonical(result),'{}',digest({}),'technical-readonly-audit',time.time()))
   print(json.dumps(result),flush=True)
   if not result['all_zero']:raise RuntimeError('IP zero audit failed; exact readback review required')
