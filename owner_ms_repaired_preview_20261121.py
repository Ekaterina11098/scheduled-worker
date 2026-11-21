"""Read-only repaired physical stock check; never calls WB or sends messages."""
import json,time
import tg_agent_new as g
from stock_china_mgt import read_store,policy
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
ROOT='technical:owner-ms-repaired-preview:2026-11-21'
data={'status':'reading','started':time.time(),'stock_writes':0}
try:
 g.check_run_budget=lambda:None
 msk,unresolved=g.load_ms_stocks_dict()
 china,china_unresolved,observed=read_store(g)
 articles='013-erminiabag-beige 018-junebag-black 020-adelebag-black 143-reginabag-black'.split()
 new='338-cristinebag-ebony 339-cristinebag-black 340-elodiebag-darkred 341-elodiebag-black 342-elodiebag-coffee 343-colettebag-black 344-colettebag-darkred 345-aureliebag-black 346-aureliebag-coffee 354-odettebag-black 355-odettebag-coffee 356-noemibag-black 357-noemibag-coffee 358-celestebag-green 359-celestebag-darkred 360-celestebag-coffee 361-celestebag-black 362-celineabag-black 363-celineabag-darkred 364-celineabag-coffee 365-celineabag-green'.split()
 data.update(status='complete',finished=time.time(),msk_articles=len(msk),china_articles=len(china),msk={a:msk.get(a) for a in articles},new_china={a:china.get(a) for a in new},unresolved=unresolved,china_unresolved=china_unresolved,proofs=g.MS_STOCK_REPORT_PROOFS)
except Exception as exc:data.update(status='stopped',error=str(exc),error_type=type(exc).__name__)
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'cloud-owner-readonly',time.time()))
seal('ms-repaired-preview',data)
print(json.dumps({'status':data['status'],'stock_writes':0}))
if data['status']!='complete':raise SystemExit(1)
