"""Read-only all-movement diagnostic. Operational responses remain in the private journal."""
import os,json,time
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
import requests
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,canonical,digest,Stopped
from stock_execution_fence import cloud_writer
ROOT=os.environ['OWNER_AUDIT_ROOT'];BASE='https://api.moysklad.ru/api/remap/1.2'
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True)
   data=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
   def save():
    with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(data),ROOT))
   data.update(status='reading',started=time.time(),requests=0,errors=[],coverage=[],documents={},reports={},audits={});save()
   session=requests.Session();session.headers.update({'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip','X-Lognex-Accept-Timezone':'Europe/Moscow'})
   def get(url,**params):
    if not url.startswith(BASE+'/'):raise Stopped('Read URL outside MS API')
    for attempt in range(3):
     response=session.get(url,params=params,timeout=90);data['requests']+=1
     if response.status_code==429 and attempt<2:
      wait=max(1,float(response.headers.get('Retry-After','1')))
      if wait>60:raise Stopped('MS provider cooldown exceeds short retry')
      time.sleep(wait);continue
     if response.status_code!=200:raise Stopped(str(response.status_code)+' '+response.text[:1800])
     time.sleep(.22)
     return response.json()
    raise Stopped('MS retry exhausted')
   def rows(url,**params):
    output=[];seen=set()
    while url:
     if url in seen:raise Stopped('Pagination loop')
     seen.add(url);v=get(url,**params);params={}
     if not isinstance(v.get('rows'),list):raise Stopped('Rows missing')
     output.extend(v['rows']);url=v.get('meta',{}).get('nextHref')
    return output
   def attempt(label,fn):
    data['phase']=label;save()
    try:
     value=fn();save();return value
    except Exception as exc:
     data['errors'].append({'phase':label,'type':type(exc).__name__,'error':str(exc)});save();return None
   art=data['approval']['article'].casefold()
   now=datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
   start=data['approval']['from'];end=now
   try:
    products=rows(BASE+'/entity/assortment',search=data['approval']['search'],limit=100)
    selected=[v for v in products if str(v.get('article','')).strip().casefold()==art]
    if not selected:raise Stopped('Exact assortment missing')
    data['products']=selected
    refs={v['meta']['href'] for v in selected}
    stores=rows(BASE+'/entity/store');data['stores']=stores
    msk=[v for v in stores if v['name']=='МСК']
    if len(msk)!=1:raise Stopped('MSK identity ambiguous')
    store=msk[0]['meta']['href']
    for product in selected:
     href=product['meta']['href'];ident=product['id']
     for name,path,params in [
      ('turnover_all','/report/turnover/all',{'filter':'product='+href+';store='+store,'momentFrom':start,'momentTo':end}),
      ('turnover_operations','/report/turnover/byoperations',{'filter':'product='+href+';store='+store,'momentFrom':start,'momentTo':end}),
      ('turnover_all_stores','/report/turnover/bystore',{'filter':'product='+href,'momentFrom':start,'momentTo':end}),
      ('stock_now','/report/stock/bystore',{'filter':'assortment='+href+';stockMode=all'}),
      ('stock_operations','/report/byoperations/stock',{'filter':'assortment='+href+';store='+store}),
      ('reserve_operations','/report/byoperations/reserve',{'filter':'assortment='+href+';store='+store})]:
      value=attempt(name+':'+ident,lambda path=path,params=params:rows(BASE+path,**params))
      if value is not None:data['reports'][name+':'+ident]=value;save()
    types=['demand','supply','move','enter','loss','salesreturn','purchasereturn','inventory','retaildemand','retailsalesreturn','processing','productionstagecompletion','customerorder']
    for kind in types:
     found={}
     for basis,flt in [('moment','moment>='+start+';moment<='+end),('updated','updated>='+start+';updated<='+end)]:
      docs=attempt(kind+':'+basis,lambda kind=kind,flt=flt:rows(BASE+'/entity/'+kind,filter=flt,limit=100,expand='positions.assortment'))
      if docs is None:continue
      data['coverage'].append({'type':kind,'basis':basis,'filter':flt,'scanned':len(docs)})
      for d in docs:found[d['id']]=d
      save()
     for ident,d in found.items():
      positions=d.get('positions',{});parts=positions.get('rows')
      if parts is None:
       parts=attempt(kind+':positions:'+ident,lambda kind=kind,ident=ident:rows(BASE+'/entity/'+kind+'/'+ident+'/positions',limit=1000,expand='assortment'))
      elif positions.get('meta',{}).get('size',len(parts))>len(parts):
       parts=attempt(kind+':positions_all:'+ident,lambda kind=kind,ident=ident:rows(BASE+'/entity/'+kind+'/'+ident+'/positions',limit=1000,expand='assortment'))
      if parts is None:continue
      matches=[p for p in parts if p.get('assortment',{}).get('meta',{}).get('href') in refs or str(p.get('assortment',{}).get('article','')).casefold()==art]
      if not matches:continue
      clean={k:v for k,v in d.items() if k!='positions'};clean['matched_positions']=matches;clean['document_type']=kind
      data['documents'][kind+':'+ident]=clean;save()
     # Full audit history of every matching document, including apply/unapply and position changes.
     for key,d in list(data['documents'].items()):
      if d['document_type']!=kind:continue
      events=attempt('audit:'+key,lambda kind=kind,d=d:rows(BASE+'/entity/'+kind+'/'+d['id']+'/audit',limit=1000))
      if events is not None:data['audits'][key]=events;save()
    data.update(status='complete' if not data['errors'] else 'partial',completed=time.time(),business_writes=0,period={'from':start,'to':end});save()
    seal('all-movement-audit',data);print(json.dumps({'status':data['status'],'documents':len(data['documents']),'coverage':len(data['coverage']),'errors':len(data['errors']),'business_writes':0}))
   except Exception as exc:
    data.update(status='stopped',error=str(exc),error_type=type(exc).__name__);save();seal('movement-audit-error',error(exc));raise
