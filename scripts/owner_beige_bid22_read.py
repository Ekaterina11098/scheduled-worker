import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_beige_competitive_bid:2026-11-22:v1';CID=42022679;NM=2215883910
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();old=io.get(ROOT)
 if old and old.get('status')=='complete':print('Already complete; no repeat');return
 v=old or dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if not old:assert io.create(ROOT,v)
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v0/bids/recommendations')or m=='POST'and u.path=='/api/advert/v1/bids/min'
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'
  else:ok=False
  assert ok,'Read-only request scope';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def save():io.put(ROOT,v)
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:350]
  save()
 def ad(path,params=None,body=None):
  time.sleep(1.3);r=requests.request('POST'if body is not None else'GET','https://advert-api.wildberries.ru'+path,params=params,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,50))
  if not r.ok:raise ValueError(str(r.status_code)+': '+r.text[:350])
  return dict(observed_at=now(),response=r.json())
 stage('campaign',lambda:ad('/api/advert/v2/adverts',dict(ids=str(CID),owner_read=time.time_ns())))
 stage('competitive',lambda:ad('/api/advert/v0/bids/recommendations',dict(advertId=CID,nmId=NM)))
 stage('minimum',lambda:ad('/api/advert/v1/bids/min',body=dict(advert_id=CID,nm_ids=[NM],payment_type='cpc',placement_types=['recommendation'])))
 stage('prices',lambda:current_prices(io,[NM]))
 stage('stock',lambda:read_stock(['5-furcoat-beige'],warehouse_role='msk'))
 stage('published',lambda:published_stock(io,v['prices'],[NM]))
 def econ():
  b=io.get('china_agent:advertising_full_growth:2026-11-22:v1:inputs')
  return model_rows(dict(products=b['own'],prices=v['prices'],stock=v['stock'],fx=b['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 stage('economics',econ)
 v['status']='complete'if not v['errors']else'complete_with_gaps';v['completed_at']=now();save();print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()

