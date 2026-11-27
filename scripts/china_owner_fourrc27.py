"""Four RC owner audit read only, preserve each stage."""
import json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_moysklad_read import Reader
from china_morning_readiness import current_prices,published_stock
io=AdvertisingIO();root='china_agent:owner_fourrc27:v1';scope=io.get(root+':scope');out=io.get(root+':result')or dict(status='reading',errors={},wb_writes=0,telegram_calls=0)
if out.get('status')=='complete':raise SystemExit('Saved')
if not io.get(root+':result'):assert io.create(root+':result',out)
orig=requests.sessions.Session.request
def guard(s,method,url,*a,**k):
 u=urlparse(url);p=u.path;m=method.upper()
 ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and p.startswith('/rest/v1/')or u.hostname=='advert-api.wildberries.ru'and(m=='GET'and p=='/api/advert/v2/adverts'or m=='POST'and p=='/api/advert/v1/bids/min')or u.hostname=='api.moysklad.ru'and m=='GET'and p.startswith('/api/remap/1.2/')or u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and p=='/api/v2/list/goods/filter'or u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and p=='/api/v3/stocks/2126188'
 assert ok,'Read-only endpoints only';return orig(s,m,url,*a,**k)
requests.sessions.Session.request=guard
def req(path,method='GET',body=None):
 time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token},timeout=(10,40));r.raise_for_status();return r.json()
def stage(k,fn):
 if k in out:return
 try:out[k]=dict(observed_at=datetime.now(timezone.utc).isoformat(),data=fn())
 except Exception as ex:out['errors'][k]=type(ex).__name__+': '+str(ex)[:220]
 io.put(root+':result',out)
try:
 stage('campaigns',lambda:req('/api/advert/v2/adverts?ids='+','.join(map(str,scope['campaign_ids']))))
 stage('prices',lambda:current_prices(io,scope['ids']))
 if 'prices'in out:stage('published_msk',lambda:published_stock(io,out['prices']['data'],scope['ids']))
 stage('gua_stock',lambda:Reader().stock([r['article']for r in scope['gua']],'guangzhou'))
 def currency():
  r=requests.get('https://api.moysklad.ru/api/remap/1.2/entity/currency',headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip'},timeout=(10,40));r.raise_for_status()
  return [{k:x.get(k)for k in('name','isoCode','default','rate')}for x in r.json()['rows']]
 stage('currency',currency)
 for c in out.get('campaigns',{}).get('data',{}).get('adverts',[]):
  typ='search'if c['settings']['placements'].get('search')else'recommendation'
  stage('min_'+str(c['id']),lambda c=c,typ=typ:req('/api/advert/v1/bids/min','POST',dict(advert_id=c['id'],nm_ids=[x['nm_id']for x in c['nm_settings']],payment_type='cpc',placement_types=[typ])))
 out.update(status='complete_with_gaps'if out['errors']else'complete',completed_at=datetime.now(timezone.utc).isoformat());io.put(root+':result',out)
finally:requests.sessions.Session.request=orig
print(json.dumps(dict(status=out['status'],errors=out['errors'])))
