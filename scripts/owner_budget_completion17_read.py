"""One owner-requested current balance audit and exact MSK economics for41332083."""
import os,copy,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse,quote
import requests
ROOT='china_agent:owner_budget_completion:2026-11-17:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 from china_advertising_state import AdvertisingIO
 from china_cloud_cost_control import Cache,WB,validate_identity
 from china_morning_readiness import current_prices,published_stock
 from china_moysklad_read import read_stock
 from china_advertising_economic_review import model_rows
 from china_budget_ready_model import assess_campaign
 from china_advertising_v2 import history
 io=AdvertisingIO();scope=io.get(ROOT+':scope');assert scope['owner_id']==5122667182 and scope['wb_writes']==0
 if not io.create(ROOT+':read_claim',dict(status='collecting',at=stamp())):
  assert io.create(ROOT+':read_resume1_claim',dict(status='collecting',at=stamp(),reason='First checkpoint PATCH targeted missing cache row; only read requests occurred')),'Resume already claimed'
 validate_identity(Cache(),WB())
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);p=u.path;m=method.upper()
  if u.hostname==urlparse(io.url).hostname:ok=p.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and p=='/api/advert/v2/adverts'or m=='POST'and p in('/api/advert/v2/budget','/api/advert/v1/bids/min')
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and p=='/api/v2/list/goods/filter'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p=='/api/v3/stocks/2126188'and set(kw.get('json')or{})=={'chrtIds'}
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/')
  else:ok=False
  assert ok,'Read-only evidence scope rejected'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 result=io.get(ROOT+':fresh')or dict(status='collecting',observed_at=stamp(),wb_writes=0,telegram_calls=0,model_calls=0,errors={})
 if not io.get(ROOT+':fresh'):assert io.create(ROOT+':fresh',result)
 def save():io.put(ROOT+':fresh',result)
 def stage(key,fn):
  if key in result and key not in result['errors']:return result[key]
  try:result[key]=fn()
  except Exception as e:result['errors'][key]=type(e).__name__+': '+str(e)[:250];save();raise
  save();return result[key]
 def req(path,method='GET',body=None):
  time.sleep(.8);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=(10,50));r.raise_for_status();return r.json()
 try:
  b=io.db('telegram_api_cache?cache_key=eq.'+quote('china_agent:advertising_artifacts:2026-11-17:v2',safe='')+'&select=bundle:payload->bundle')[0]['bundle']
  ids=sorted(c['id']for c in b['campaigns']);states=stage('campaigns',lambda:dict(observed_at=stamp(),adverts=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts']))
  assert {c['id']for c in states['adverts']}==set(ids),'Campaign coverage incomplete'
  live=[c['id']for c in states['adverts']if c['status']in(9,11)]
  budgets=stage('budgets',lambda:dict(observed_at=stamp(),rows=req('/api/advert/v2/budget','POST',dict(advertIds=live))['adverts']))
  assert {r['advertId']for r in budgets['rows']}==set(live),'Budget coverage incomplete'
  for row in budgets['rows']:assert row.get('currency')=='CNY'or row.get('currency')in('',None)and row['total']==0
  cp=next(c for c in states['adverts']if c['id']==41332083);assert cp['status']==11 and cp['currency']=='CNY'
  nms=[n['nm_id']for n in cp['nm_settings']]
  prices=stage('prices',lambda:current_prices(io,sorted({n['nm_id']for c in states['adverts']if c['status']in(9,11)for n in c['nm_settings']})))
  exact=dict(prices,rows=[r for r in prices['rows']if r['nm_id']in nms]);articles=[r['article']for r in exact['rows']]
  def stock():
   parts=[read_stock(articles[i:i+20],warehouse_role='msk')for i in range(0,len(articles),20)]
   assert all(p['coverage_complete']for p in parts)
   return dict(parts[0],rows=[r for p in parts for r in p['rows']],observed_at=stamp(),read_attempts=sum(p['read_attempts']for p in parts))
  stocks=stage('stock413',stock);pub=stage('published413',lambda:published_stock(io,exact,nms))
  assert not pub['missing_nm_ids']
  stage('minimum413',lambda:req('/api/advert/v1/bids/min','POST',dict(advert_id=41332083,nm_ids=nms,payment_type='cpc',placement_types=['search'])))
  source=io.get('china_agent:advertising_source:2026-11-17:v2');inputs=io.get('china_agent:advertising_full_growth:2026-11-17:v1:inputs')
  models=model_rows(dict(products=inputs['own'],prices=exact,stock=stocks,fx=inputs['fx']),io.get('china_agent:new_ad_economics_policy:v1'),{})
  # Existing approved, dated MSK logistics are reused, never replaced by zero.
  if models['missing']:
   delivery={'rows':{r['article']:dict(delivery_cny=source['economics']['rows'][str(r['nm_id'])]['logistics_cny'],delivery_source=source['economics']['rows'][str(r['nm_id'])]['logistics_source'],route='Moscow_FBS')for r in exact['rows']}}
   models=model_rows(dict(products=inputs['own'],prices=exact,stock=stocks,fx=inputs['fx']),io.get('china_agent:new_ad_economics_policy:v1'),delivery)
  assert not models['missing'] and set(models['rows'])==set(map(str,nms)),'Complete current own model required'
  for nm,e in models['rows'].items():e.update(published_stock=pub['amounts'][nm],published_stock_observed_at=pub['observed_at'],fx_rub_per_cny=inputs['fx']['rub_per_cny'])
  source['economics']['rows'].update(models['rows']);raw=next(r for batch in source['batches'].values()for r in (batch['stats']or[])if r['advertId']==41332083)
  model=assess_campaign(cp,raw,source['economics'],inputs['own'],history(source.get('executions',[])),b['budget_days'],stamp())
  model['expected_bids']={str(n['nm_id']):n['bids_kopecks']for n in cp['nm_settings']};model['member_inputs']={str(r['nm_id']):dict(article=r['article'],price=r['seller_price'],cost=models['rows'][str(r['nm_id'])]['own_cogs_rub'],buyout=models['rows'][str(r['nm_id'])]['buyout'],fx=inputs['fx']['rub_per_cny'])for r in exact['rows']}
  result.update(model413=model,models413=models,fx=inputs['fx'],status='complete',completed_at=stamp());save()
  print(json.dumps(dict(status='complete',campaigns=len(ids),live=len(live),model_base=model['modeled_after_ads_cny'],model_stress=model['stress_after_ads_cny'],wb_writes=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

