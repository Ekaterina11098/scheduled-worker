"""Supplement incomplete read endpoints and compare raw WB order identities; never stock writes."""
import os,json,time
from datetime import datetime,timezone,timedelta
import requests
from stock_deploy_support import runtime_db,seal
from stock_operation_store import Store,canonical,Stopped
from stock_execution_fence import cloud_writer
from stock_shared_requests import SharedRequests
ROOT=os.environ['OWNER_AUDIT_ROOT'];BASE='https://api.moysklad.ru/api/remap/1.2'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);d=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
   if d['status']=='reading':raise Stopped('First read audit still active')
   d['supplement']={'started':time.time(),'status':'reading','errors':[]};x=d['supplement']
   def save():
    with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(d),ROOT))
   save();session=requests.Session();shared=SharedRequests(s)
   def request(method,url,token,**kw):
    isms=url.startswith(BASE+'/')
    if not (isms and method=='GET') and not (url.startswith('https://marketplace-api.wildberries.ru/api/v3/') and ((method=='GET' and url.endswith('/orders')) or (method=='POST' and ('/stocks/' in url or url.endswith('/orders/status'))))):raise Stopped('Read-only scope')
    if not isms:shared.acquire(token,url)
    r=session.request(method,url,headers={'Authorization':('Bearer ' if isms else '')+token,'Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip','X-Lognex-Accept-Timezone':'Europe/Moscow'},timeout=90,**kw)
    if not isms:shared.observe(token,url,r.status_code,r.headers)
    if r.status_code!=200:raise Stopped(str(r.status_code)+' '+r.text[:1500])
    time.sleep(.22);return r.json()
   def rows(url,**params):
    out=[]
    while url:
     v=request('GET',url,os.environ['MOYSKLAD_API_TOKEN'],params=params);params={}
     out+=v['rows'];url=v.get('meta',{}).get('nextHref')
    return out
   def attempt(k,fn):
    x['phase']=k;save()
    try:x[k]=fn()
    except Exception as exc:x['errors'].append({'phase':k,'error':str(exc)})
    save()
   product=d['products'][0];href=product['meta']['href'];art=d['approval']['article']
   refs={p['meta']['href'] for p in d['products']}
   attempt('stock_now',lambda:rows(BASE+'/report/stock/bystore',filter='product='+href+';stockMode=all'))
   attempt('stock_operations',lambda:rows(BASE+'/report/byoperations/stock',filter='assortment='+href))
   attempt('reserve_operations',lambda:rows(BASE+'/report/byoperations/reserve',filter='assortment='+href))
   def retry_moves():
    docs=rows(BASE+'/entity/move',filter='moment>='+d['period']['from']+';moment<='+d['period']['to'],limit=100,expand='positions.assortment')
    found=[]
    for doc in docs:
     parts=doc.get('positions',{}).get('rows',[])
     if doc.get('positions',{}).get('meta',{}).get('size',0)>len(parts):parts=rows(BASE+'/entity/move/'+doc['id']+'/positions',expand='assortment',limit=1000)
     match=[v for v in parts if v.get('assortment',{}).get('meta',{}).get('href') in refs]
     if match:
      doc['positions']={'rows':match};found.append(doc)
    return {'scanned':len(docs),'matched':found}
   attempt('move_moment_retry',retry_moves)
   def wb():
    src=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',('technical:stock-daily:2026-11-20:0700',)).fetchone()[0])['source'];db.commit()
    cards=[v for v in src['cards'][2] if v['vendorCode'].casefold()==art]
    if len(cards)!=1:raise Stopped('Exact China card missing')
    card=cards[0];token=os.environ['WB_TOKEN_3'];url='https://marketplace-api.wildberries.ru/api/v3/orders'
    start=int(datetime.fromisoformat(d['approval']['from']).replace(tzinfo=timezone(timedelta(hours=3))).timestamp())
    nxt=0;allorders=[];pages=0
    while True:
     response=request('GET',url,token,params={'limit':1000,'next':nxt,'dateFrom':start,'dateTo':int(time.time())});pages+=1
     if not isinstance(response.get('orders'),list):raise Stopped('WB orders missing')
     allorders+=response['orders'];new=response.get('next')
     if not response['orders'] or not new or new==nxt:break
     nxt=new
     if pages>100:raise Stopped('WB pagination limit')
    orders=[o for o in allorders if o.get('nmId')==card['nmID'] or o.get('chrtId') in {v['chrtID'] for v in card['sizes']} or str(o.get('article','')).casefold()==art]
    statuses=request('POST','https://marketplace-api.wildberries.ru/api/v3/orders/status',token,json={'orders':[o['id'] for o in orders]}) if orders else {}
    stocks=request('POST','https://marketplace-api.wildberries.ru/api/v3/stocks/2126188',token,json={'chrtIds':[v['chrtID'] for v in card['sizes']]})
    return {'observed':time.time(),'pages':pages,'scanned':len(allorders),'card':card,'orders':orders,'statuses':statuses,'stocks':stocks}
   attempt('wb_raw',wb)
   x.update(status='complete' if not x['errors'] else 'partial',completed=time.time());save();seal('full-movement-supplement',x)
   print(json.dumps({'status':x['status'],'errors':len(x['errors']),'business_writes':0}))
