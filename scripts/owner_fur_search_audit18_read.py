"""Exact two-fur price, category minimum and public Moscow comparison; read only."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_moysklad_read import read_stock
ROOT='china_agent:owner_fur_search_audit:2026-11-18:v1';IDS=[2216217906,2216257724,2216045897,2215883910,2216111729,2216167898]
def stamp():return datetime.now(timezone.utc).isoformat()
io=AdvertisingIO();assert io.create(ROOT+':claim',dict(status='collecting',at=stamp()))
v=dict(status='collecting',observed_at=stamp(),errors={},wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
original=requests.sessions.Session.request
def guard(session,method,url,*args,**kw):
 u=urlparse(url);m=method.upper();p=u.path
 if u.hostname==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and p.startswith('/rest/v1/')
 elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config'))or(m=='POST'and p=='/api/advert/v1/bids/min')
 elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and p=='/api/v2/list/goods/filter'
 elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p=='/api/v3/stocks/2126188'
 elif u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='POST'and p in('/api/v2/search-report/table/details','/api/v2/search-report/product/search-texts')
 elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and p=='/content/v2/get/cards/list'
 elif u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/')
 elif u.hostname=='card.wb.ru':ok=m=='GET'and p in('/cards/v4/detail','/cards/v2/detail')
 elif u.hostname=='search.wb.ru':ok=m=='GET'and p=='/exactmatch/ru/common/v9/search'
 else:ok=False
 assert ok,'Only authorized reads allowed '+m+' '+str(u.hostname)+p
 return original(session,method,url,*args,**kw)
requests.sessions.Session.request=guard
def get(host,path,params=None,body=None,auth=True):
 time.sleep(.6)
 r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers={'Authorization':io.token}if auth else{},timeout=(8,25))
 if not r.ok:raise ValueError('HTTP '+str(r.status_code)+' '+host+path+': '+r.text[:180])
 return r.json()
def stage(k,fn):
 try:v[k]=dict(observed_at=stamp(),data=fn())
 except Exception as ex:v['errors'][k]=str(ex)[:350]
 io.put(ROOT+':fresh',v)if io.get(ROOT+':fresh')else io.create(ROOT+':fresh',v)
try:
 stage('states',lambda:get('advert-api.wildberries.ru','/api/advert/v2/adverts',dict(ids='41756218,41925305')))
 stage('config',lambda:get('advert-api.wildberries.ru','/api/advert/v1/config'))
 for mode in('cpm','cpc'):
  stage('minimum_'+mode,lambda mode=mode:get('advert-api.wildberries.ru','/api/advert/v1/bids/min',body=dict(advert_id=41925305,nm_ids=IDS,payment_type=mode,placement_types=['search','recommendation'])))
 prices=[]
 for nm in IDS:
  stage('seller_'+str(nm),lambda nm=nm:get('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',dict(limit=1000,offset=0,filterNmID=nm)))
  stage('card_'+str(nm),lambda nm=nm:[{k:c.get(k)for k in('nmID','title','description','dimensions','characteristics','sizes','subjectID','subjectName','vendorCode')} for c in get('content-api.wildberries.ru','/content/v2/get/cards/list',body=dict(settings=dict(cursor=dict(limit=100),filter=dict(textSearch=str(nm),withPhoto=-1))))['cards']if c['nmID']==nm])
 stage('msk_stock',lambda:read_stock(['1-furcoat-whitemelange','2-furcoat-beigemelange','3-furcoat-chocolate','5-furcoat-beige','6-furcoat-gray','7-furcoat-black'],warehouse_role='msk'))
 size_ids=[]
 for nm in IDS:
  for card in v.get('card_'+str(nm),{}).get('data',[]):
   size_ids +=[s['chrtID']for s in card.get('sizes',[])]
 if size_ids:stage('published_stock',lambda:get('marketplace-api.wildberries.ru','/api/v3/stocks/2126188',body=dict(chrtIds=size_ids)))
 def search_report(which):
  body=dict(currentPeriod=dict(start='2026-11-11',end='2026-11-17'),pastPeriod=dict(start='2026-11-04',end='2026-11-10'),nmIds=IDS,includeSubstitutedSKUs=True,includeSearchTexts=True,orderBy=dict(field='openCard',mode='desc'))
  if which=='details':body.update(positionCluster='all',limit=100,offset=0)
  else:body.update(topOrderBy='openCard',limit=30)
  return get('seller-analytics-api.wildberries.ru','/api/v2/search-report/'+('table/details' if which=='details'else'product/search-texts'),body=body)
 stage('search_details',lambda:search_report('details'))
 if 'search_details' not in v['errors']:
  time.sleep(21);stage('search_texts',lambda:search_report('texts'))
 v.update(status='complete_with_gaps'if v['errors']else'complete',completed_at=stamp());io.put(ROOT+':fresh',v)
 print(json.dumps(dict(status=v['status'],errors=v['errors'],wb_writes=0,model_calls=0),ensure_ascii=True))
finally:requests.sessions.Session.request=original

