"""Read-only diagnostic of global MS catalogue/report coverage; no marketplace writes."""
import time,json
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
ROOT='technical:owner-ms-zero-coverage:2026-11-21'
data={'status':'reading','started':time.time(),'stock_writes':0}
try:
 g.check_run_budget=lambda:None
 def read(path,**params):
  v=g.api('GET',g.MS_API+path,g.MS_TOKEN,wb=False,retry_read_network=True,params=dict(limit=3,offset=0,**params))
  return {'meta':v.get('meta'),'rows':[{'id':r.get('id'),'article':r.get('article'),'archived':r.get('archived'),'name':r.get('name'),'meta':r.get('meta'),'stockByStore':r.get('stockByStore'),'stock':r.get('stock'),'reserve':r.get('reserve'),'quantity':r.get('quantity')} for r in v.get('rows',[])]}
 store=g.MS_API+'/entity/store/3c67619d-f25d-11ee-0a80-0c6f000a027a'
 china=g.MS_API+'/entity/store/2233c6a7-d906-11f1-0a80-197e004df0d2'
 data['msk_all_quantities']=read('/report/stock/all',filter='store='+store+';stockMode=all;quantityMode=all',groupBy='variant')
 data['china_all_quantities']=read('/report/stock/all',filter='store='+china+';stockMode=all;quantityMode=all',groupBy='variant')
 data['msk_current']=read('/report/stock/bystore/current',stockType='stock',include='zeroLines',filter='storeId=3c67619d-f25d-11ee-0a80-0c6f000a027a')
 data.update(status='complete',finished=time.time())
except Exception as exc:data.update(status='stopped',error=str(exc),error_type=type(exc).__name__)
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'cloud-owner-readonly',time.time()))
seal('ms-coverage-diagnostic',data)
print(json.dumps({'status':data['status'],'stock_writes':0}))
if data['status']!='complete':raise SystemExit(1)
