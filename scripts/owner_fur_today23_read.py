import requests,time,os,copy,json
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_fur_today:2026-11-23:v1';IDS=[2215883910,2216111729,2216167898,2216217906,2216257724,2216045897]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':print('Already complete');return
 if not v:v=dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v3/fullstats','/adv/v1/budget'))or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='POST'and u.path=='/api/analytics/v3/sales-funnel/products')or(u.hostname=='marketplace-api.wildberries.ru'and((m=='GET'and u.path=='/api/v3/orders')or(m=='POST'and u.path=='/api/v3/orders/status')));assert ok,'Fur exact read-only scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def get(host,path,params=None,body=None):
  time.sleep(1.3);r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()
 def stage(k,fn):
  if k in v:return
  try:v[k]=dict(observed_at=now(),data=fn());v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:200]
  io.put(ROOT,copy.deepcopy(v))
 stage('campaign',lambda:get('advert-api.wildberries.ru','/api/advert/v2/adverts',dict(ids='42022679',owner_read=time.time_ns())))
 stage('ads',lambda:get('advert-api.wildberries.ru','/adv/v3/fullstats',dict(ids='42022679',beginDate='2026-11-23',endDate='2026-11-23')))
 stage('budget',lambda:get('advert-api.wildberries.ru','/adv/v1/budget',dict(id=42022679)))
 body=dict(selectedPeriod={'start':'2026-11-23','end':'2026-11-23'},pastPeriod={'start':'2026-11-22','end':'2026-11-22'},nmIds=IDS,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
 stage('funnel',lambda:get('seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products',body=body))
 def orders():
  end=datetime.now(ZoneInfo('Europe/Moscow'));start=end.replace(hour=0,minute=0,second=0,microsecond=0);cursor=0;rows=[]
  for _ in range(3):
   j=get('marketplace-api.wildberries.ru','/api/v3/orders',dict(limit=1000,next=cursor,dateFrom=int(start.timestamp()),dateTo=int(end.timestamp())))
   rows.extend(x for x in j['orders']if x['nmId']in IDS)
   if not j['orders']or len(j['orders'])<1000 or j.get('next')in(None,0,cursor):break
   cursor=j['next']
  else:raise ValueError('FBS pagination incomplete')
  return dict(cutoff=end.isoformat(),rows=[{k:x.get(k)for k in('id','nmId','article','createdAt','convertedPrice','convertedCurrencyCode','isZeroOrder')}for x in rows])
 stage('orders',orders)
 if 'orders'in v:
  ids=[x['id']for x in v['orders']['data']['rows']]
  stage('order_status',lambda:get('marketplace-api.wildberries.ru','/api/v3/orders/status',body={'orders':ids})if ids else {'orders':[]})
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()

