"""Bounded owner119 checkout read; no business writes, preserve stages."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
c=Cache();ROOT='china_agent:owner_checkout119_27:v1';scope=c.get(ROOT+':scope');ids={x['nm']for x in scope['items']};assert len(ids)==119
out=c.get(ROOT+':result')or dict(status='reading',started_at=datetime.now(timezone.utc).isoformat(),errors={},wb_writes=0,telegram_calls=0)
if out.get('status')=='complete':raise SystemExit('Already saved')
original=requests.sessions.Session.request
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper()
 ok=(u.hostname==urlparse(c.url).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(m=='GET'and((u.hostname in('discounts-prices-api.wildberries.ru','dp-calendar-api.wildberries.ru')and u.path in('/api/v2/list/goods/filter','/api/v1/calendar/promotions','/api/v1/calendar/promotions/nomenclatures'))or(u.hostname=='card.wb.ru'and u.path=='/cards/v4/detail')))
 assert ok,'Only exact read endpoints';return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
token=os.environ['WB_TOKEN_3']
def get(host,path,p,auth=True):
 time.sleep(.7);r=requests.get('https://'+host+path,params=p,headers={'Authorization':token}if auth else{},timeout=(8,22))
 if not r.ok:raise ValueError('HTTP '+str(r.status_code)+' '+host+path)
 return r.json()
def stage(k,fn):
 if k in out or k=='buyer_0'and k in out.get('errors',{}):return
 try:out[k]=dict(observed_at=datetime.now(timezone.utc).isoformat(),data=fn());out['errors'].pop(k,None)
 except Exception as e:out['errors'][k]=str(e)[:220]
 c.put(ROOT+':result',out)
try:
 def seller():
  rows=[]
  for page in range(4):
   part=get('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',dict(limit=1000,offset=1000*page))['data']['listGoods'];rows+=part
   if len(part)<1000:return [x for x in rows if x['nmID']in ids]
  raise ValueError('Catalog exceeds bounded4pages')
 stage('seller',seller)
 def promotions():
  j=get('dp-calendar-api.wildberries.ru','/api/v1/calendar/promotions',dict(startDateTime='2026-11-26T00:00:00Z',endDateTime='2026-11-28T23:59:59Z',allPromo=True,limit=1000,offset=0))
  return j
 stage('promotions',promotions)
 promos=out.get('promotions',{}).get('data',{}).get('data',{}).get('promotions',[])
 for promo in promos[:8]:
  pid=promo.get('id')
  if pid:
   def members(pid=pid):
    rows=[]
    for page in range(4):
     j=get('dp-calendar-api.wildberries.ru','/api/v1/calendar/promotions/nomenclatures',dict(promotionID=pid,inAction=True,limit=1000,offset=1000*page));part=j.get('data',{}).get('nomenclatures',[]);assert isinstance(part,list);rows+=part
     if len(part)<1000:return dict(raw_count=len(rows),rows=[r for r in rows if r.get('id',r.get('nmID'))in ids],promotion=promo)
    raise ValueError('Promo exceeds bounded4pages')
   stage('promo_'+str(pid),members)
 # One known public endpoint, two bounded batches; stop after first access failure.
 for i in range(0,119,60):
  key='buyer_'+str(i)
  stage(key,lambda i=i:get('card.wb.ru','/cards/v4/detail',dict(appType=1,curr='rub',dest=-1257786,spp=30,nm=';'.join(map(str,sorted(ids)[i:i+60]))),False))
  if key in out['errors']:break
 out['status']='complete_with_gaps'if out['errors']else'complete';out['completed_at']=datetime.now(timezone.utc).isoformat();c.put(ROOT+':result',out);print(json.dumps(dict(status=out['status'],errors=out['errors'])))
finally:requests.sessions.Session.request=original
