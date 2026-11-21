"""Read-only source binding audit for owner-approved single belt pool."""
import os,json,time
from urllib.parse import urlparse
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
from stock_ms_complete_report import read_store_report
ROOT='technical:owner-belt-pool-binding:2026-11-21'
data={'status':'reading','started':time.time(),'stock_writes':0}
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);shared=SharedRequests(s,budget=lambda:None);g.STOCK_REQUEST_GATE=shared;g.check_run_budget=lambda:None
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'cloud-owner-readonly',data['started']))
   try:
    goods=g.ms_rows(g.MS_API+'/entity/assortment',filter='archived=false;archived=true')
    codes={'2044635464934','2044635464941','2044635464927','2044635464958'}
    selected=[]
    for p in goods:
     text=' '.join(str(p.get(k)or'') for k in ['name','article','code','externalCode']).casefold()
     barcodes={str(v) for b in p.get('barcodes',[]) for v in b.values()}
     if ('belt' in text or 'ремень' in text) and ('choc' in text or 'шокол' in text) or codes & barcodes:
      selected.append(p)
    stores=g.ms_rows(g.MS_API+'/entity/store')
    msk=[v for v in stores if v.get('id')=='3c67619d-f25d-11ee-0a80-0c6f000a027a']
    if len(msk)!=1:raise RuntimeError('Exact Moscow store missing')
    rows=read_store_report(g,msk[0],goods);byid={urlparse(r['meta']['href']).path.rsplit('/',1)[-1]:r for r in rows}
    data['products']=[dict(product={k:p.get(k) for k in ['id','article','name','code','externalCode','barcodes','archived','meta']},stock=byid.get(p.get('id'),{}).get('stock'),reserve=byid.get(p.get('id'),{}).get('reserve')) for p in selected]
    data['exact_matches']=[p['id'] for p in goods if g.norm(p.get('article'))=='5belts-chocolate']
    data['source_complete']=True;save()
    original=g.requests.request
    def bounded(method,url,**kw):kw['timeout']=(5,12);return original(method,url,**kw)
    g.requests.request=bounded
    try:
     reply=g.api('POST',g.WB_CONTENT+'/content/v2/get/cards/list',g.cabinet_tokens()[1],json={'settings':{'cursor':{'limit':100},'filter':{'withPhoto':-1,'textSearch':'454004208'}}})
     data['wb_cards']=[{k:c.get(k) for k in ['nmID','vendorCode','sizes','createdAt','updatedAt']} for c in reply.get('cards',[]) if c.get('nmID')==454004208]
    except Exception as exc:data['wb_card_error']=str(exc)
    finally:g.requests.request=original
    data.update(status='complete',finished=time.time());save()
   except Exception as exc:data.update(status='stopped',error=str(exc),error_type=type(exc).__name__);save()
seal('belt-pool-binding',data)
print(json.dumps({'status':data['status'],'stock_writes':0}))
if data['status']!='complete':raise SystemExit(1)
