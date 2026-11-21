"""Read-only Moscow FBS route and actual processing evidence. No buyer personal data saved."""
import requests,json,time,re
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_msk_delivery_review:2026-11-21:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)or dict(status='collecting',started_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 def save():io.put(ROOT,v)if io.get(ROOT)else io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url)
  if (u.hostname or'').endswith('wildberries.ru'):assert method.upper()=='GET'and(u.path in('/api/v3/warehouses','/api/v3/offices','/api/v3/supplies','/api/v3/orders')or re.fullmatch('/api/v3/supplies/[^/]+/orders',u.path)),'Only logistics reads'
  if 'telegram'in(u.hostname or'')or'openai'in(u.hostname or''):raise ValueError('No TG/model')
  return orig(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def get(path,params=None):
  time.sleep(.7);r=requests.get('https://marketplace-api.wildberries.ru'+path,params=params,headers={'Authorization':io.token,'Cache-Control':'no-cache'},timeout=(8,35));r.raise_for_status();return r.json()
 def stage(k,fn):
  if k in v:return
  try:v[k]=dict(data=fn(),observed_at=now());v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:160]
  save()
 stage('warehouses',lambda:get('/api/v3/warehouses'))
 def offices():
  data=get('/api/v3/offices');ids={w.get('officeId')for w in v.get('warehouses',{}).get('data',[])}
  return dict(total=len(data),linked=[x for x in data if x.get('id')in ids],moscow_candidates=[x for x in data if any(a in str(x.get('name','')).lower()for a in('коледино','подольск','электросталь','внуково','жуковск','черная грязь','чёрная грязь'))][:25])
 stage('offices',offices)
 stage('supplies',lambda:get('/api/v3/supplies',dict(limit=30,next=0)))
 def orders():
  data=get('/api/v3/orders',dict(limit=200,next=0,dateFrom=int(datetime(2026,11,18,tzinfo=timezone.utc).timestamp()),dateTo=int(datetime.now(timezone.utc).timestamp())))
  rows=data.get('orders',[]);keys=('id','createdAt','supplyId','warehouseId','officeId','nmId','article','deliveryType','cargoType','isB2B','convertedPrice','currencyCode','convertedCurrencyCode')
  return dict(raw_count=len(rows),next=data.get('next'),msk_rows=[{k:r.get(k)for k in keys}for r in rows if r.get('warehouseId')==2126188][:80],fur_rows=[{k:r.get(k)for k in keys}for r in rows if r.get('nmId')in(2215883910,2216111729,2216167898)])
 stage('orders_sample',orders)
 v.update(status='complete_with_gaps'if v['errors']else'complete',completed_at=now());save();print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()
