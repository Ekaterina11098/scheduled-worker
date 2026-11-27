"""Owner63 read-only readiness; no WB mutation/Telegram/model."""
import json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
ROOT='china_agent:owner_winners63_27:v1';io=AdvertisingIO();scope=io.get(ROOT+':scope');ids=[x['nm']for x in scope['items']];assert len(ids)==63
out=io.get(ROOT+':result')or dict(status='reading',errors={},started_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0)
if out.get('status')=='complete':raise SystemExit('Saved complete')
if not io.get(ROOT+':result'):assert io.create(ROOT+':result',out)
original=requests.sessions.Session.request
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper();p=u.path
 ok=(u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and p.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and ((m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/promotion/count'))or(m=='POST'and p in('/api/advert/v1/bids/min','/api/advert/v2/budget'))))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and p=='/api/v2/list/goods/filter')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and p=='/api/v3/stocks/2126188')or(u.hostname=='api.moysklad.ru'and m=='GET'and p=='/api/remap/1.2/entity/currency')
 assert ok,'Read-only endpoints';return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
def req(path,method='GET',body=None):
 time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token},timeout=(8,40));r.raise_for_status();return r.json()if r.content else{}
def stage(k,fn):
 if k in out:return
 try:out[k]=dict(observed_at=datetime.now(timezone.utc).isoformat(),data=fn());out['errors'].pop(k,None)
 except Exception as e:out['errors'][k]=type(e).__name__+': '+str(e)[:220]
 io.put(ROOT+':result',out)
try:
 stage('config',lambda:req('/api/advert/v1/config'))
 stage('listing',lambda:req('/adv/v1/promotion/count'))
 def campaigns():
  n=sorted({x['advertId']for g in out['listing']['data']['adverts']for x in g.get('advert_list',[])})
  return sum([req('/api/advert/v2/adverts?ids='+','.join(map(str,n[j:j+50])))['adverts']for j in range(0,len(n),50)],[])
 stage('campaigns',campaigns)
 stage('prices',lambda:current_prices(io,ids))
 if 'prices'in out:stage('published',lambda:published_stock(io,out['prices']['data'],ids))
 active=[c['id']for c in out.get('campaigns',{}).get('data',[])if c['status']in(9,11)]
 if active:stage('budgets',lambda:req('/api/advert/v2/budget','POST',dict(advertIds=active)))
 def currency():
  r=requests.get('https://api.moysklad.ru/api/remap/1.2/entity/currency',headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip'},timeout=(10,40));r.raise_for_status()
  return [{k:x.get(k)for k in('name','code','isoCode','rate','default','system','archived')}for x in r.json()['rows']]
 stage('cost_currency_metadata',currency)
 for c in out.get('campaigns',{}).get('data',[]):
  if c['status']not in(9,11)or c['id']==42088552:continue
  found=[n['nm_id']for n in c['nm_settings']if n['nm_id']in ids]
  for z in('search','recommendations'):
   if found and c['settings']['placements'].get(z):
    typ='recommendation'if z=='recommendations'else z
    stage('min_'+str(c['id'])+'_'+z,lambda c=c,found=found,typ=typ:req('/api/advert/v1/bids/min','POST',dict(advert_id=c['id'],nm_ids=found,payment_type='cpc',placement_types=[typ])))
 out['status']='complete_with_gaps'if out['errors']else'complete';out['completed_at']=datetime.now(timezone.utc).isoformat();io.put(ROOT+':result',out)
finally:requests.sessions.Session.request=original
print(json.dumps({'status':out['status'],'errors':out['errors']}))
