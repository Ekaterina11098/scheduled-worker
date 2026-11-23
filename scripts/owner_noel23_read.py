import json,time,requests,os,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_moysklad_read import read_stock
ROOT='china_agent:owner_noel_ad_coverage:2026-11-23:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':print('Already complete');return
 if not v:v=dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and m=='GET'and u.path in('/adv/v1/promotion/count','/api/advert/v2/adverts'))or(u.hostname=='api.moysklad.ru'and m=='GET')or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='GET'and u.path=='/api/v1/analytics/banned-products/blocked')
  assert ok,'Noel read-only scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:300]
  io.put(ROOT,copy.deepcopy(v))
 def get(host,path,params=None):
  time.sleep(1.5);r=requests.get('https://'+host+path,params=params,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()
 stage('catalogue',lambda:dict(observed_at=io.get('china_agent:prices:v1')['observed_at'],rows=[{'nm_id':r['nmID'],'article':r['vendorCode']}for r in io.get('china_agent:prices:v1')['rows']if'noel'in r['vendorCode'].lower()]))
 stage('listing',lambda:get('advert-api.wildberries.ru','/adv/v1/promotion/count'))
 if 'listing'in v:
  ids=sorted({x['advertId']for g in v['listing'].get('adverts',[])if g['status']in(4,9,11)for x in g['advert_list']})
  for n in range(0,len(ids),50):stage('campaigns_'+str(n),lambda n=n:get('advert-api.wildberries.ru','/api/advert/v2/adverts',dict(ids=','.join(map(str,ids[n:n+50])),owner_read=time.time_ns())))
 stage('stock',lambda:read_stock([r['article']for r in v['catalogue']['rows']],warehouse_role='msk'))
 stage('blocked',lambda:[x for x in get('seller-analytics-api.wildberries.ru','/api/v1/analytics/banned-products/blocked',{'sort':'nmId','order':'asc'})['report']if x['nmId']in {r['nm_id']for r in v['catalogue']['rows']}])
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()

