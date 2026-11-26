"""Owner15 current campaign/minimum/stock/economics read only; no mutations."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import Reader
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_reach15_27:v1';io=AdvertisingIO();scope=io.get(ROOT+':scope');ids=[x['nm']for x in scope['items']];assert len(ids)==15
out=io.get(ROOT+':result')or dict(status='reading',errors={},started_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0)
if out.get('status')=='complete':raise SystemExit('Already saved')
original=requests.sessions.Session.request
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper();p=u.path
 ok=(u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and p.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and ((m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config'))or(m=='POST'and p in('/api/advert/v1/bids/min','/api/advert/v2/budget'))))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and p=='/api/v2/list/goods/filter')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and p=='/api/v3/stocks/2126188')or(u.hostname=='api.moysklad.ru'and m=='GET'and p.startswith('/api/remap/1.2/'))
 assert ok,'Read-only campaign/model endpoints';return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
def req(path,method='GET',body=None):
 time.sleep(1);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token},timeout=(8,35))
 if not r.ok:raise ValueError('HTTP '+str(r.status_code)+' '+path)
 return r.json()if r.content else{}
def stage(k,fn):
 if k in out:return
 try:out[k]=dict(observed_at=datetime.now(timezone.utc).isoformat(),data=fn());out['errors'].pop(k,None)
 except Exception as e:out['errors'][k]=str(e)[:220]
 io.put(ROOT+':result',out)
try:
 stage('campaigns',lambda:req('/api/advert/v2/adverts?ids='+','.join(map(str,scope['campaign_ids']))))
 stage('prices',lambda:current_prices(io,ids))
 stage('stock',lambda:Reader().stock([x['article']for x in scope['items']],'msk'))
 if 'prices'in out:stage('published',lambda:published_stock(io,out['prices']['data'],ids))
 def econ():
  inp=io.get('china_agent:advertising_full_growth:2026-11-26:v1:inputs:midday')
  return model_rows(dict(products=inp['own'],prices=out['prices']['data'],stock=out['stock']['data'],fx=inp['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 if 'prices'in out and 'stock'in out:stage('economics',econ)
 for campaign in out.get('campaigns',{}).get('data',{}).get('adverts',[]):
  found=[n for n in campaign['nm_settings']if n['nm_id']in ids]
  for zone in('search','recommendation'):
   # Quote existing members only; no invalid nonmember92 quote.
   if found:
    stage('min_'+str(campaign['id'])+'_'+zone,lambda campaign=campaign,found=found,zone=zone:req('/api/advert/v1/bids/min','POST',dict(advert_id=campaign['id'],nm_ids=[n['nm_id']for n in found],payment_type='cpc',placement_types=[zone])))
 out['status']='complete_with_gaps'if out['errors']else'complete';out['completed_at']=datetime.now(timezone.utc).isoformat();io.put(ROOT+':result',out);print(json.dumps({'status':out['status'],'errors':out['errors']}))
finally:requests.sessions.Session.request=original
