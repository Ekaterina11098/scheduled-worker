import os,json,time,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner119_boost:2026-11-23:v1'
def main():
 io=AdvertisingIO()
 if io.get(ROOT):print('Already read');return
 v=dict(status='reading',wb_writes=0,telegram_calls=0,model_calls=0,observed_at=datetime.now(timezone.utc).isoformat(),errors={});assert io.create(ROOT,v)
 def stage(k,fn):
  try:v[k]=fn()
  except Exception as e:v['errors'][k]=type(e).__name__+': '+str(e)[:250]
  io.put(ROOT,v)
 def get(host,path,params=None,body=None):
  time.sleep(1.5);r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()
 stage('campaign',lambda:get('advert-api.wildberries.ru','/api/advert/v2/adverts',dict(ids='41155909',owner_read=time.time_ns())))
 stage('competitive',lambda:get('advert-api.wildberries.ru','/api/advert/v0/bids/recommendations',dict(advertId=41155909,nmId=1473243898)))
 stage('minimum',lambda:get('advert-api.wildberries.ru','/api/advert/v1/bids/min',body=dict(advert_id=41155909,nm_ids=[1473243898],payment_type='cpc',placement_types=['recommendation'])))
 stage('budget',lambda:get('advert-api.wildberries.ru','/api/advert/v2/budget',body=dict(advertIds=[41155909])))
 for nm in [1473243898,1473242756]:stage('price:'+str(nm),lambda nm=nm:get('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',dict(limit=100,offset=0,filterNmID=nm)))
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=datetime.now(timezone.utc).isoformat());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()
