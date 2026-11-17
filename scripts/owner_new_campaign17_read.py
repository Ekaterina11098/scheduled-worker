"""One bounded read-only proposal check. No model, Telegram or WB mutations."""
import os,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from china_moysklad_read import read_stock
from china_morning_readiness import published_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_new_campaign:2026-11-17:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();scope=c.get(ROOT+':scope');assert scope['status']=='authorized_read_only' and scope['owner_id']==5122667182
 assert c.create(ROOT+':read_claim',dict(status='collecting',at=now())),'Already claimed; inspect saved stages'
 io=AdvertisingIO();original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();p=u.path;body=kw.get('json')or{}
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=p.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config'))or(m=='POST'and p=='/api/advert/v1/bids/min')
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and p=='/api/v2/list/goods/filter'
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and p=='/content/v2/get/cards/list'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p=='/api/v3/stocks/2126188'and set(body)=={'chrtIds'}
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/')
  else:ok=False
  assert ok,'Forbidden transport '+m+' '+str(u.hostname)+p
  return original(session,method,url,*args,**kw)
 validate_identity(c,WB());requests.sessions.Session.request=guard
 v=dict(status='collecting',observed_at=now(),wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False,errors={})
 def stage(k,fn):
  try:v[k]=fn()
  except Exception as e:v['errors'][k]=type(e).__name__+': '+str(e)[:220]
  c.put(ROOT+':fresh',v)
 try:
  def campaigns():
   rows=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,scope['campaign_ids'])))['adverts']
   assert {x['id']for x in rows}==set(scope['campaign_ids'])
   return dict(observed_at=now(),rows=rows)
  stage('campaigns',campaigns)
  def prices():
   out=[]
   for nm in scope['nm_ids']:
    rows=io.wb('/api/v2/list/goods/filter?limit=1000&offset=0&filterNmID='+str(nm))['listGoods']
    rows=[r for r in rows if r['nmID']==nm];assert len(rows)==1
    r=rows[0];values={s['discountedPrice']for s in r['sizes']};assert len(values)==1 and r['currencyIsoCode4217']=='CNY'
    out.append(dict(nm_id=nm,article=r['vendorCode'],currency='CNY',seller_price=next(iter(values)),discount=r['discount'],size_ids=[s['sizeID']for s in r['sizes']]))
   return dict(rows=out,observed_at=now())
  stage('prices',prices)
  stage('stock',lambda:read_stock(scope['articles'],warehouse_role='msk'))
  stage('published',lambda:published_stock(io,v['prices'],scope['nm_ids']))
  def categories():
   out=[]
   for nm in scope['nm_ids']:
    time.sleep(.8);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token},json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':str(nm),'withPhoto':-1}}},timeout=(10,40));r.raise_for_status()
    cards=[x for x in r.json()['cards']if x['nmID']==nm];assert len(cards)==1
    out.append({k:cards[0][k]for k in('nmID','vendorCode','subjectID')})
   return dict(rows=out,observed_at=now())
  stage('categories',categories)
  def minimum():
   cp=next(x for x in v['campaigns']['rows']if x['id']==41298169);n=next(x for x in cp['nm_settings']if x['subject']['id']==50)
   return dict(quote=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=cp['id'],nm_ids=[n['nm_id']],payment_type='cpc',placement_types=['search'])),reference_nm=n['nm_id'],subject_id=50,observed_at=now(),basis='same_subject_existing_member_owner_rule')
  stage('minimum',minimum)
  stage('config',lambda:dict(value=http(io,'/api/advert/v1/config'),observed_at=now()))
  def economics():
   result=model_rows(dict(products=scope['products'],prices=v['prices'],stock=v['stock'],fx=dict(rub_per_cny=scope['fx_rub_per_cny'])),c.get('china_agent:new_ad_economics_policy:v1'),c.get('china_agent:expected_profit_delivery_model:v1'))
   for nm,e in result['rows'].items():e.update(published_stock=v['published']['amounts'].get(nm),published_stock_observed_at=v['published']['observed_at'],fx_rub_per_cny=scope['fx_rub_per_cny'])
   assert not result['missing'];return result
  stage('economics',economics)
  v.update(status='complete'if not v['errors']else'partial',completed_at=now());c.put(ROOT+':fresh',v)
  print(json.dumps(dict(status=v['status'],errors=v['errors'],wb_writes=0,telegram_calls=0,model_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
