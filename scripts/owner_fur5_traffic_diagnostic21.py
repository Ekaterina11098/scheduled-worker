"""Scoped fur5 traffic diagnostic: read-only WB, MSK and public Moscow context."""
import copy,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
ROOT='china_agent:owner_fur5_traffic_diagnostic:2026-11-21:v1'
IDS=[2215883910,2216111729,2216167898]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)or dict(status='collecting',started_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 def save():io.put(ROOT,json.loads(json.dumps(v)))if io.get(ROOT)else io.create(ROOT,json.loads(json.dumps(v)))
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);host=u.hostname or'';m=method.upper();p=u.path
  if host==urlparse(io.url).hostname:return original(session,method,url,*a,**kw)
  ok=(host=='advert-api.wildberries.ru'and((m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v3/fullstats'))or(m=='POST'and p in('/api/advert/v1/bids/min','/api/advert/v2/budget','/adv/v2/supplier/nms'))))or(host=='discounts-prices-api.wildberries.ru'and m=='GET'and p=='/api/v2/list/goods/filter')or(host=='marketplace-api.wildberries.ru'and m=='POST'and p=='/api/v3/stocks/2126188')or(host=='content-api.wildberries.ru'and m=='POST'and p=='/content/v2/get/cards/list')or(host=='api.moysklad.ru'and m=='GET')or(host=='card.wb.ru'and m=='GET'and p in('/cards/v4/detail','/cards/v2/detail'))
  assert ok,'Only diagnostic reads allowed'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None,params=None,host='advert-api.wildberries.ru',auth=True):
  time.sleep(1.2);r=requests.request(method,'https://'+host+path,json=body,params=params,headers={**({'Authorization':io.token}if auth else{}),'Cache-Control':'no-cache, no-store','Pragma':'no-cache'},timeout=(8,35));r.raise_for_status();return r.json()
 def stage(key,fn):
  if key in v:return
  try:v[key]=dict(observed_at=now(),data=fn());v['errors'].pop(key,None)
  except Exception as ex:v['errors'][key]=type(ex).__name__+': '+str(ex)[:160]
  save()
 stage('campaign',lambda:req('/api/advert/v2/adverts',params=dict(ids=42022679,_owner_read_nonce=time.time_ns())))
 stage('budget',lambda:req('/api/advert/v2/budget','POST',dict(advertIds=[42022679])))
 stage('config',lambda:req('/api/advert/v1/config'))
 stage('prices',lambda:current_prices(io,IDS))
 stage('msk',lambda:read_stock(['5-furcoat-beige','6-furcoat-gray','7-furcoat-black']))
 if 'prices'in v:stage('published',lambda:published_stock(io,v['prices']['data'],IDS))
 stage('minimum',lambda:req('/api/advert/v1/bids/min','POST',dict(advert_id=42022679,nm_ids=IDS,payment_type='cpc',placement_types=['recommendation','search'])))
 def eligibility():
  data=req('/adv/v2/supplier/nms','POST',[4377])
  assert isinstance(data,list),'Unknown eligibility schema'
  return dict(total_category_rows=len(data),matches=[r for r in data if int(r.get('nm',r.get('nmId',r.get('nm_id',0))))in IDS],schema_keys=list(data[0])if data else[])
 stage('eligible',eligibility)
 for nm in IDS:
  def card(nm=nm):
   data=req('/content/v2/get/cards/list','POST',dict(settings=dict(cursor=dict(limit=100),filter=dict(textSearch=str(nm),withPhoto=-1))),host='content-api.wildberries.ru')
   rows=[c for c in data['cards']if c['nmID']==nm];assert len(rows)==1
   c=rows[0];return {k:c.get(k)for k in('nmID','imtID','subjectID','subjectName','vendorCode','brand','title','sizes','photos','video','dimensions','characteristics','createdAt','updatedAt','needKiz','isProhibited','isDeleted','isValid')}
  stage('card_'+str(nm),card)
 def public(version):
  data=req('/cards/v'+str(version)+'/detail',params=dict(appType=1,curr='rub',dest=-1257786,spp=30,nm=';'.join(map(str,IDS)),_owner_read_nonce=time.time_ns()),host='card.wb.ru',auth=False)
  rows=data.get('products',data.get('data',{}).get('products'));assert isinstance(rows,list)
  return dict(context='Moscow dest=-1257786 public unauthenticated no wallet personalization',products=[{k:c.get(k)for k in('id','name','subjectId','supplierId','colors','rating','reviewRating','feedbacks','sizes','totalQuantity','time1','time2','priceU','salePriceU','logisticsCost','promotions','isNew','isAdult')}for c in rows if c['id']in IDS])
 stage('public_v4',lambda:public(4))
 if 'public_v4'not in v:stage('public_v2',lambda:public(2))
 def stats():
  data=req('/adv/v3/fullstats',params=dict(ids=42022679,beginDate='2026-11-19',endDate='2026-11-21'))
  rows=[]
  for cp in data:
   assert cp['advertId']==42022679
   for d in cp['days']:
    bynm={}
    for app in d.get('apps',[]):
     for n in app.get('nms',[]):
      nm=n['nmId'];t=bynm.setdefault(nm,dict(nm_id=nm,views=0,clicks=0,atbs=0,orders=0,sum=0,sum_price=0))
      for k in('views','clicks','atbs','orders','sum','sum_price'):t[k]+=n.get(k,0)
    rows.append(dict(day=d['date'],products=list(bynm.values())))
  return rows
 stage('stats',stats)
 v.update(status='complete_with_gaps'if v['errors']else'complete',completed_at=now());save();print(json.dumps(dict(status=v['status'],errors=v['errors'],wb_writes=0)))
if __name__=='__main__':main()
