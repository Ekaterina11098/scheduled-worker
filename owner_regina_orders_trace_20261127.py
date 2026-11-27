"""Owner-requested read-only WB order/status reconciliation for Regina."""
import os,json,time,requests
from datetime import datetime,timezone
from stock_deploy_support import runtime_db
from stock_operation_store import Store,canonical,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
ROOT='technical:owner-full-movement:2026-11-27:regina1'
BASE='https://api.moysklad.ru/api/remap/1.2'
with cloud_writer(runtime_db()):
 with runtime_db() as db:
  s=Store(db,postgres=True);d=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
  shared=SharedRequests(s);out={'started':time.time(),'cabinets':[],'errors':[],'business_writes':0}
  def save():
   d['wb_fresh']=out
   with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(d),ROOT))
  def request(method,url,token,**kw):
   isms=url.startswith(BASE+'/')
   assert (isms and method=='GET') or (not isms and (method=='GET' or (method=='POST' and url.endswith('/orders/status'))))
   if not isms:shared.acquire(token,url)
   r=requests.request(method,url,headers={'Authorization':('Bearer ' if isms else '')+token,'Accept':'application/json;charset=utf-8','X-Lognex-Accept-Timezone':'Europe/Moscow'},timeout=90,**kw)
   if not isms:shared.observe(token,url,r.status_code,r.headers)
   r.raise_for_status();return r.json()
  href=d['products'][0]['meta']['href']
  for key,path in [('reserve_operations','/report/byoperations/reserve'),('stock_operations','/report/byoperations/stock')]:
   try:
    url=BASE+path;rows=[];params={'filter':'assortment='+href}
    while url:
     v=request('GET',url,os.environ['MOYSKLAD_API_TOKEN'],params=params);params={};rows+=v['rows'];url=v.get('meta',{}).get('nextHref');time.sleep(.25)
    out[key]=rows
   except Exception as exc:out['errors'].append({'phase':key,'error':str(exc)})
  save()
  for i in range(3):
   token=os.environ['WB_TOKEN_'+str(i+1)];host='https://marketplace-api.wildberries.'+('cn' if i==2 else 'ru')
   orders=[];nxt=0;seen=set();scanned=0
   while True:
    assert nxt not in seen;seen.add(nxt)
    v=request('GET',host+'/api/v3/orders',token,params={'limit':1000,'next':nxt,'dateFrom':int(datetime(2026,11,18,21,tzinfo=timezone.utc).timestamp()),'dateTo':int(out['started'])})
    assert isinstance(v.get('orders'),list) and 'next' in v
    scanned+=len(v['orders'])
    for o in v['orders']:
     if str(o.get('article','')).strip().casefold()=='143-reginabag-black':
      orders.append({k:o.get(k) for k in ('id','article','createdAt','warehouseId','supplyId','nmId','chrtId','orderUid','deliveryType')})
    if not v['orders'] or not v['next']:break
    nxt=v['next']
   statuses=[]
   for offset in range(0,len(orders),1000):
    ids=[o['id'] for o in orders[offset:offset+1000]]
    statuses+=request('POST',host+'/api/v3/orders/status',token,json={'orders':ids})['orders']
   assert {o['id'] for o in orders}=={o['id'] for o in statuses}
   out['cabinets'].append({'cabinet':i,'pages':len(seen),'scanned':scanned,'orders':orders,'statuses':statuses});save()
  out.update(complete=True,finished=time.time());save()
  print(json.dumps({'complete':True,'cabinets':3,'orders':sum(len(c['orders']) for c in out['cabinets']),'business_writes':0}))
