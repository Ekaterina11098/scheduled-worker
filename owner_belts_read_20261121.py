"""Read only one IP belt card and per-size FBS responses; no writes or messages."""
import json,time
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
ROOT='technical:owner-belts-read:2026-11-21'
data={'status':'reading','stock_writes':0,'started':time.time()}
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);shared=SharedRequests(s,budget=lambda:None);g.STOCK_REQUEST_GATE=shared;g.check_run_budget=lambda:None
   try:
    token=g.cabinet_tokens()[1]
    reply=g.api('POST',g.WB_CONTENT+'/content/v2/get/cards/list',token,json={'settings':{'cursor':{'limit':100},'filter':{'withPhoto':-1,'textSearch':'454004208'}}},retry_read_network=True)
    cards=reply.get('cards')
    if not isinstance(cards,list):raise RuntimeError('Card response missing')
    selected=[c for c in cards if c.get('nmID')==454004208 and g.norm(c.get('vendorCode'))=='5belts-chocolate']
    if len(selected)!=1:raise RuntimeError('Exact current belt card identity not confirmed')
    card=selected[0];data['card']={k:card.get(k) for k in ['nmID','vendorCode','sizes','title','createdAt','updatedAt']}
    ids=sorted({z.get('chrtID',z.get('chrtId')) for z in card['sizes']})
    warehouses=g.api('GET',g.WB_MARKET+'/api/v3/warehouses',token,retry_read_network=True)
    if not isinstance(warehouses,list):raise RuntimeError('Warehouse response missing')
    data['warehouses']=[{k:w.get(k) for k in ['id','name','isDeleting','isProcessing']} for w in warehouses]
    data['stocks']={}
    for w in warehouses:
     wh=w['id'];result=g.api('POST',g.WB_MARKET+'/api/v3/stocks/'+str(wh),token,json={'chrtIds':ids},retry_read_network=True)
     data['stocks'][str(wh)]=result
    primary=data['stocks'].get('854652',{}).get('stocks',[])
    seen={v.get('chrtId') for v in primary}
    data['individual_missing']={}
    for ident in ids:
     if ident not in seen:data['individual_missing'][str(ident)]=g.api('POST',g.WB_MARKET+'/api/v3/stocks/854652',token,json={'chrtIds':[ident]},retry_read_network=True)
    data['ms_exact_products']=g.ms_rows(g.MS_API+'/entity/product',filter='article=5belts-chocolate')
    data['ms_search_products']=[{k:p.get(k) for k in ['id','article','name','archived']} for p in g.ms_rows(g.MS_API+'/entity/product',search='5belts')]
    data.update(status='complete',finished=time.time())
   except Exception as exc:data.update(status='stopped',error=str(exc),error_type=type(exc).__name__)
   with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),'{}',digest({}),'cloud-owner-readonly',time.time()))
seal('belts-readonly',data)
print(json.dumps({'status':data['status'],'stock_writes':0}))
if data['status']!='complete':raise SystemExit(1)
