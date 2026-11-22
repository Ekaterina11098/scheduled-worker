import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_more_growth:2026-11-22:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();scope=io.get(ROOT+':scope');assert scope['status']=='authorized_read_only'and scope['owner_id']==5122667182
 old=io.get(ROOT+':fresh')
 if old and old.get('status')=='complete':print('Already complete');return
 v=old or dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if not old:assert io.create(ROOT+':fresh',v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v1/promotion/count')or m=='POST'and u.path=='/api/advert/v1/bids/min'
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'
  else:ok=False
  assert ok,'Read-only scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT+':fresh',v)
 def ad(path,params=None,body=None):
  time.sleep(1.3);r=requests.request('POST'if body is not None else'GET','https://advert-api.wildberries.ru'+path,params=params,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store','Pragma':'no-cache'},timeout=(10,55));r.raise_for_status();return r.json()
 def camps():
  listing=ad('/adv/v1/promotion/count');ids={x['advertId']for g in listing.get('adverts',[])if g['status']in(9,11)for x in g['advert_list']};rows=ad('/api/advert/v2/adverts',dict(ids=','.join(map(str,ids)),owner_read=time.time_ns()))['adverts'];byid={r['id']:r for r in rows};byid[41270309]=ad('/api/advert/v2/adverts',dict(ids='41270309',owner_read=time.time_ns()))['adverts'][0];return list(byid.values())
 stage('campaigns',camps);stage('prices',lambda:current_prices(io,scope['nms']));stage('raw_prices',lambda:io.prices([str(n)for n in scope['price_nms']]))
 stage('stock',lambda:read_stock([r['article']for r in v['prices']['rows']],warehouse_role='msk'));stage('published',lambda:published_stock(io,v['prices'],scope['nms']))
 def econ():
  b=io.get('china_agent:advertising_full_growth:2026-11-22:v1:inputs');result=model_rows(dict(products=b['own'],prices=v['prices'],stock=v['stock'],fx=b['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
  for row in result['rows'].values():
   if row.get('buyout_fallback')and row.get('sample_size')==0:
    q=.4;fee=1-sum(row[k]for k in('commission_pct','tax_pct','payment_reserve_pct'))/100;row['buyout']=q;row['planned_buyout_source']='owner-economics-new-model-own-buyout-first-20261111:bags40';row['expected_margin_before_ads_cny']=q*(row['seller_price_cny']*fee-row['own_cogs_rub']/row['fx_rub_per_cny'])-row['logistics_cny']-row.get('handling_rub',0)/row['fx_rub_per_cny']
  return result
 stage('economics',econ)
 def minimum():
  c=next(c for c in v['campaigns']if c['id']==41270309);assert c['status']==9;nm=next(n['nm_id']for n in c['nm_settings']if n['subject']['id']==50)
  return dict(campaign_id=41270309,representative_nm=nm,observed_at=now(),quote=ad('/api/advert/v1/bids/min',body=dict(advert_id=41270309,nm_ids=[nm],payment_type='cpc',placement_types=['recommendation'])))
 stage('minimum',minimum);v['status']='complete'if not v['errors']else'complete_with_gaps';v['completed_at']=now();io.put(ROOT+':fresh',v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()

