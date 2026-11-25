"""Fresh exact Guangzhou campaign diagnosis only; no business writes, TG or models."""
import json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices
from china_moysklad_read import Reader
from china_campaign_routes import guangzhou_models
ROOT='china_agent:owner_gua25_evening:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO()
 if io.get(ROOT):print('Existing checkpoints retained; no repeat');return
 validate_identity(Cache(),WB());out=dict(status='reading',started_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,out)
 def save():io.put(ROOT,json.loads(json.dumps(out)))
 orig=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();p=u.path
  ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and p.startswith('/rest/v1/')
  if u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/');time.sleep(.5)
  if u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and p=='/api/v2/list/goods/filter'
  if u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p=='/api/v3/stocks/2373413'
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and p in('/api/advert/v2/adverts','/adv/v3/fullstats','/api/advert/v1/config')or m=='POST'and p in('/api/advert/v1/bids/min','/api/advert/v2/budget')
  assert ok,'Read-only exact Guangzhou investigation'
  return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(host,path,params=None,body=None):
  time.sleep(1.4);r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers={'Authorization':io.token},timeout=(8,50))
  if not r.ok:raise ValueError('HTTP '+str(r.status_code)+' '+path)
  return r.json()
 def stage(k,fn):
  try:out[k]=fn()
  except Exception as ex:out['errors'][k]=type(ex).__name__+': '+str(ex)[:200]
  save()
 try:
  c=req('advert-api.wildberries.ru','/api/advert/v2/adverts',dict(ids='41779660'))['adverts'];assert len(c)==1 and c[0]['id']==41779660 and c[0]['currency']=='CNY';out['campaign']=c[0];save()
  ids=sorted(n['nm_id']for n in c[0]['nm_settings']);route=copy.deepcopy(io.get('china_agent:campaign_economics_routes:v1')['campaigns']['41779660']);assert set(ids)==set(route['nm_ids'])and route['warehouse_id']=='2233c6a7-d906-11f1-0a80-197e004df0d2'and route['published_warehouse_id']==2373413
  out['route']=route;save()
  stage('budget',lambda:req('advert-api.wildberries.ru','/api/advert/v2/budget',body=dict(advertIds=[41779660])))
  stage('today_stats',lambda:req('advert-api.wildberries.ru','/adv/v3/fullstats',dict(ids='41779660',beginDate='2026-11-25',endDate='2026-11-25')))
  stage('history_stats',lambda:req('advert-api.wildberries.ru','/adv/v3/fullstats',dict(ids='41779660',beginDate='2026-11-22',endDate='2026-11-24')))
  stage('minimum',lambda:req('advert-api.wildberries.ru','/api/advert/v1/bids/min',body=dict(advert_id=41779660,nm_ids=ids,payment_type='cpc',placement_types=['recommendation'])))
  stage('prices',lambda:current_prices(io,ids))
  if 'prices'in out:
   stage('stock',lambda:Reader().stock([p['article']for p in out['prices']['rows']],'guangzhou'))
   cards=io.get('china_agent:campaign_route_cards:v1:41779660');assert {r['nmID']for r in cards['rows']}==set(ids);out['cards']=cards;save()
   mapping={str(z['chrtID']):c['nmID']for c in cards['rows']for z in c['sizes']}
   stage('published',lambda:dict(warehouse_id=2373413,size_to_nm=mapping,observed_at=now(),raw=req('marketplace-api.wildberries.ru','/api/v3/stocks/2373413',body=dict(chrtIds=list(map(int,mapping))))))
  if all(k in out for k in ('stock','published','cards')):
   def economics():
    v=dict(io.get('china_agent:advertising_full_growth:2026-11-25:v1:inputs:midday'),prices=out['prices']);return guangzhou_models(v,route,dict(stock=out['stock'],published=out['published'],cards=out['cards']),io.get('china_agent:new_ad_economics_policy:v1'))
   stage('economics',economics)
  out.update(status='complete_with_gaps'if out['errors']else'complete',completed_at=now());save();print(json.dumps(dict(status=out['status'],errors=out['errors'],items=len(ids),wb_writes=0,telegram_calls=0)))
 finally:requests.sessions.Session.request=orig
if __name__=='__main__':main()
