import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal
from stock_operation_store import Store,canonical,digest
from stock_shared_requests import SharedRequests
from stock_execution_fence import cloud_writer
ROOT='technical:guangzhou-new-inspect:2026-11-16'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);shared=SharedRequests(s);g.STOCK_REQUEST_GATE=shared
   g.check_run_budget=lambda:None;g._CACHE_GET=lambda k:None;g._CACHE_SET=lambda *a:None
   rows=g.api('GET',g.WB_MARKET+'/api/v3/warehouses',g.cabinet_tokens()[2],retry_read_network=True)
   data={'warehouses':rows,'observed_at':time.time()}
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest(data),'read-only',time.time()))
   seal('warehouses',data)
   print('Warehouse inspection saved')
