"""One bounded read of the twelve approved price experiments. No business mutations or TG."""
import json,time,requests
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse,urlencode
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_hourly_sales_read import read_orders,select_rows,aggregate
from china_wb_evidence import Reports,FUNNEL,normalize_funnel
ROOT='china_agent:owner_changes25_review2100:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO()
 if io.get(ROOT):print('Existing checkpoint retained; no repeat');return
 validate_identity(Cache(),WB());end=datetime.now(ZoneInfo('Europe/Moscow'));items=io.get(ROOT+':scope')['items']
 ids={x['nm_id']for x in items};assert len(ids)==45
 out=dict(status='reading',observed_at=now(),cut_msk=end.isoformat(),items=items,orders={},errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,out)
 def save():io.put(ROOT,json.loads(json.dumps(out)))
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);method=method.upper();ok=u.hostname==urlparse(io.url).hostname and method in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  if u.hostname=='marketplace-api.wildberries.ru':ok=method=='GET'and u.path in('/api/v3/orders','/api/v3/orders/new')
  if u.hostname=='advert-api.wildberries.ru':ok=method=='GET'and u.path=='/adv/v3/fullstats'
  if u.hostname=='seller-analytics-api.wildberries.ru':ok=method=='POST'and u.path=='/api/analytics/v3/sales-funnel/products'and set(kw.get('json',{}).get('nmIds',[]))==ids
  assert ok,'Read-only exact experiment followup scope'
  return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,params=None):
  time.sleep(1);r=requests.get('https://marketplace-api.wildberries.ru'+path,params=params,headers={'Authorization':io.token},timeout=55)
  if not r.ok:raise ValueError('Orders HTTP '+str(r.status_code))
  return r.json()
 try:
  new=req('/api/v3/orders/new')['orders']
  for d in (0,1):
   cut=end-timedelta(days=d);start=cut.replace(hour=0,minute=0,second=0,microsecond=0)
   raw=read_orders(req,start,cut);raw.update({r['id']:r for r in new});rows=select_rows(raw.values(),start,cut)
   out['orders'][str(d)]=dict(status='complete',rows=[r for r in rows if r['nmId']in ids],start_msk=start.isoformat(),end_msk=cut.isoformat(),observed_at=now());save()
  try:
   latest=io.get('china_agent:hourly_sales_api:v1:latest');snap=io.get(latest['source_key']);cids=sorted(map(int,snap['advertising']['campaigns']))
   r=requests.get('https://advert-api.wildberries.ru/adv/v3/fullstats',params=dict(ids=','.join(map(str,cids)),beginDate='2026-11-25',endDate='2026-11-25'),headers={'Authorization':io.token},timeout=55)
   assert r.ok,'Advertising HTTP '+str(r.status_code)
   out['advertising']=dict(rows=r.json(),requested_ids=cids,observed_at=now());save()
  except Exception as ex:out['errors']['advertising']=type(ex).__name__+': '+str(ex)[:180];save()
  class Adapter:
   def get(self,k):return io.get(k)
   def save(self,k,v):return io.put(k,v)if io.get(k)is not None else io.create(k,v)
   def db(self,method,table,params=None,body=None,prefer=None):
    assert table=='telegram_api_cache';return io.db(table+'?'+urlencode(params or{}),method,body,prefer)
  try:
   selected=dict(start=end.date().isoformat(),end=end.date().isoformat());pastday=(end-timedelta(days=1)).date().isoformat();past=dict(start=pastday,end=pastday)
   body=dict(selectedPeriod=selected,pastPeriod=past,nmIds=sorted(ids),brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy=dict(field='openCard',mode='desc'),limit=1000,offset=0)
   response=Reports(Adapter()).request(FUNNEL,body)
   if not response['available']:out['errors']['funnel']=dict(status=response.get('status'),retry_at=response.get('retry_at'))
   else:
    data=response['data']['data'];products=data['products'];assert data['currency']=='CNY'and {p['product']['nmId']for p in products}==ids
    out['funnel']=dict(status='complete',observed_at=response['observed_at'],rows=normalize_funnel(products,selected,past,ROOT),update_delay_hours=2,scope='all_sources',past_is_full_day=True,raw_products=products)
   save()
  except Exception as ex:out['errors']['funnel']=type(ex).__name__+': '+str(ex)[:180];save()
  out.update(status='complete'if not out['errors']else'partial',completed_at=now());save()
 finally:requests.sessions.Session.request=original
 print(json.dumps(dict(status=out['status'],errors=out['errors'],items=45,cut=out['cut_msk'],wb_writes=0,telegram_calls=0)))
if __name__=='__main__':main()
