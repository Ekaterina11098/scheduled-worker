"""Owner-requested evening diagnosis. Bounded reads; no WB mutation, TG, model or monitor."""
import os,json,time
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_sales_urgent:2026-11-16:evening:v1'
MSK=ZoneInfo('Europe/Moscow')
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();w=WB();validate_identity(c,w)
 assert datetime.now(MSK).date().isoformat()=='2026-11-16'
 if not c.create(ROOT+':claim',dict(status='collecting',at=stamp(),wb_writes=0)):raise RuntimeError('Existing collection claim; inspect instead of replay')
 out=dict(status='collecting',observed_at=stamp(),errors={},wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 def save():c.put(ROOT,out)
 def read(name,fn):
  try:out[name]=fn()
  except Exception as e:out['errors'][name]=type(e).__name__+': '+str(e)[:200]
  save()
 def get(path,params=None):
  r=requests.get('https://marketplace-api.wildberries.ru'+path,params=params,headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(10,45));r.raise_for_status();return r.json()
 def orders():
  cut=datetime.now(MSK).replace(microsecond=0);new=get('/api/v3/orders/new')['orders'];assert isinstance(new,list)
  values={}
  for offset in (0,1,7):
   end=cut-timedelta(days=offset);start=end.replace(hour=19,minute=0,second=0);found={};cursor=0
   for page in range(3):
    data=get('/api/v3/orders',dict(limit=1000,next=cursor,dateFrom=int(start.timestamp()),dateTo=int(end.timestamp())));part=data['orders'];assert isinstance(part,list)
    for r in part:found[r['id']]=r
    nxt=data.get('next')
    if not part or not nxt:break
    assert nxt!=cursor;cursor=nxt;time.sleep(.5)
   else:raise RuntimeError('Order pagination incomplete')
   for r in new:found[r['id']]=r
   rows=[]
   for r in found.values():
    at=datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'));assert at.tzinfo
    if start<=at.astimezone(MSK)<end:rows.append({k:r.get(k) for k in ('id','nmId','article','createdAt','isZeroOrder','convertedPrice','convertedCurrencyCode')})
   assert all(r['convertedCurrencyCode']==156 and type(r['convertedPrice'])in(int,float) for r in rows)
   values[str(offset)]=dict(start_msk=start.isoformat(),end_msk=end.isoformat(),observed_at=stamp(),count=len(rows),amount_cny=round(sum(r['convertedPrice']for r in rows)/100,2),rows=rows)
  return dict(status='complete',cut_msk=cut.isoformat(),basis='FBS created all statuses, dedup id; buyer amount after discounts not proceeds; not proven all sales models',periods=values)
 read('orders',orders)
 def ads():
  ids=[40933588,40945478,41055480,41298169,41925305]
  campaigns=w.campaigns(ids)
  budgets=w.req('/api/advert/v2/budget','POST',dict(advertIds=ids))
  return dict(observed_at=stamp(),campaigns=campaigns,budgets=budgets)
 read('advertising',ads)
 def quotes():return w.req('/api/advert/v1/bids/min','POST',dict(advert_id=40933588,nm_ids=[1473243906],payment_type='cpc',placement_types=['recommendation']))
 read('subject50_minimum',quotes)
 from china_morning_readiness import current_prices,published_stock
 from china_moysklad_read import read_stock
 class Prices:
  token=os.environ['WB_TOKEN_3']
  def wb(self,path):
   r=requests.get('https://discounts-prices-api.wildberries.ru'+path,headers={'Authorization':self.token},timeout=(10,45));r.raise_for_status();return r.json()['data']
 io=Prices();ids=[1473243903,1473243448,1473245505,1473244341]
 read('prices',lambda:current_prices(io,ids))
 if 'prices'in out:
  read('stock',lambda:read_stock([r['article']for r in out['prices']['rows']]))
  read('published_stock',lambda:published_stock(io,out['prices'],ids))
 out.update(status='complete'if not out['errors']else'partial',completed_at=stamp());save()
 print(json.dumps(dict(status=out['status'],errors=out['errors'],source_key=ROOT,wb_writes=0,model_calls=0,telegram_calls=0)))
if __name__=='__main__':
 old=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=method=='GET'and u.path in('/api/v3/orders','/api/v3/orders/new')or method=='POST'and u.path=='/api/v3/stocks/2126188'
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=method=='GET'and u.path in('/api/v2/list/goods/filter','/ping')
  elif u.hostname=='advert-api.wildberries.ru':ok=method=='GET'and u.path in('/api/advert/v2/adverts','/adv/v1/supplier/settings')or method=='POST'and u.path in('/api/advert/v2/budget','/api/advert/v1/bids/min')
  elif u.hostname=='api.moysklad.ru':ok=method=='GET'and u.path.startswith('/api/remap/1.2/')
  else:ok=False
  assert ok,'Read-only request scope rejected '+method+' '+(u.hostname or'')+u.path
  return old(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=old

