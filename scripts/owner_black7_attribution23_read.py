import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_black7_attribution:2026-11-23:v1';NM=2216167898;ORDER=6336254271
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();old=io.get(ROOT)
 if old and old.get('status')=='complete'and 'prior_click_window'in old:print('Already read');return
 v=old or dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if not old:assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/adv/v3/fullstats','/api/advert/v2/adverts')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/orders/status'and kw.get('json')=={'orders':[ORDER]}
  else:ok=False
  assert ok,'Read only exact attribution scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT,v)
 def get(host,path,params=None,body=None):
  time.sleep(1.2);r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store','Pragma':'no-cache'},timeout=(10,55));r.raise_for_status();return r.json()
 stage('order_status',lambda:dict(observed_at=now(),data=get('marketplace-api.wildberries.ru','/api/v3/orders/status',body={'orders':[ORDER]})))
 stage('campaign',lambda:dict(observed_at=now(),data=get('advert-api.wildberries.ru','/api/advert/v2/adverts',params=dict(ids='42022679',owner_read=time.time_ns()))))
 def ads(start='2026-11-22',ids=None):
  if ids is None:
   source=io.get('china_agent:advertising_source:2026-11-22:v2');ids=sorted({c['advertId']for b in source['batches'].values()for c in b['stats']})
  data=get('advert-api.wildberries.ru','/adv/v3/fullstats',params=dict(ids=','.join(map(str,ids)),beginDate=start,endDate='2026-11-23'))
  assert isinstance(data,list);rows=[]
  for c in data:
   for d in c.get('days',[]):
    for a in d.get('apps',[]):
     for n in a.get('nms',[]):
      if n['nmId']==NM:rows.append(dict(cid=c['advertId'],date=d['date'],app=a['appType'],**{k:n.get(k,0)for k in('orders','sum_price','sum','views','clicks','atbs')}))
  return dict(observed_at=now(),requested_campaigns=ids,returned_campaigns=[c['advertId']for c in data],rows=rows,period_from=start,period_to='2026-11-23')
 stage('advertising',ads);stage('prior_click_window',lambda:ads('2026-11-09',[41756218,41925305,42022679]));v['status']='complete'if not v['errors']else'complete_with_gaps';v['completed_at']=now();io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()

