import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_approved_warehouses import install
ROOT='technical:owner-china-cancel-status:2026-11-22'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);shared=SharedRequests(s,budget=lambda:None)
   g.STOCK_REQUEST_GATE=shared;g.STOCK_SHARED_ORDERS=shared;install(g)
   statuses=g.api('POST',g.WB_MARKET+'/api/v3/orders/status',g.cabinet_tokens()[2],json={'orders':[6322041219,6323357293]})
   data=dict(status='complete',observed_at=time.time(),orders=statuses)
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'owner-readonly',time.time()))
   seal('china-cancel-status',data)
   print('Cancellation statuses recorded; no stock writes')
