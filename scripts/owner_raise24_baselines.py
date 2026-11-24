import requests,json,time,copy,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_raise_baselines:2026-11-24:v1'
CASES=[('043',1473243914,'2026-10-25','2026-10-28'),('60',1473243912,'2026-11-08','2026-11-11')]
def main():
 io=AdvertisingIO();v=io.get(ROOT)or dict(status='reading',rows={},errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if v.get('status')=='complete':return
 if io.get(ROOT)is None:assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='POST'and u.path=='/api/analytics/v3/sales-funnel/products'and len((kw.get('json')or{}).get('nmIds',[]))==1 and (kw.get('json')or{})['nmIds'][0]in(1473243914,1473243912))
  assert ok;return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 for key,nm,start,end in CASES:
  if key in v['rows']:continue
  try:
   body=dict(selectedPeriod={'start':'2026-11-20','end':'2026-11-23'},pastPeriod={'start':start,'end':end},nmIds=[nm],brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
   time.sleep(22);r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token},json=body,timeout=(10,55));r.raise_for_status()
   v['rows'][key]=dict(request=body,response=r.json(),observed_at=datetime.now(timezone.utc).isoformat())
  except Exception as ex:v['errors'][key]=str(ex)[:250]
  io.put(ROOT,copy.deepcopy(v))
 v['status']='complete'if len(v['rows'])==2 else'complete_with_gaps';io.put(ROOT,v);print(json.dumps({'status':v['status'],'errors':v['errors']}))
if __name__=='__main__':main()
