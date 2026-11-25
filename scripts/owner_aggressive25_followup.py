"""One read-only advertising follow-up, preserve partial results and no repeated reads."""
import requests,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
KEY='china_agent:owner_aggressive25:v1:followup1457'
def main():
 io=AdvertisingIO()
 if io.get(KEY):print('Existing follow-up checkpoint retained');return
 validate_identity(Cache(),WB());base=io.get('china_agent:hourly_sales_api:v1:snapshot:2026-11-25T14:MSK');ids=base['advertising']['requested_ids']
 out=dict(status='reading',created_at=datetime.now(timezone.utc).isoformat(),requested_ids=ids,baseline_key='china_agent:owner_aggressive25:v1:read',post_change_baseline_key='china_agent:hourly_sales_api:v1:snapshot:2026-11-25T14:MSK',wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(KEY,out)
 def save():io.put(KEY,json.loads(json.dumps(out)))
 original=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();ok=u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v3/fullstats')
  assert ok,'Read-only follow-up scope';return original(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def req(path,params):
  time.sleep(1.5);r=requests.get('https://advert-api.wildberries.ru'+path,params=params,headers={'Authorization':io.token,'Cache-Control':'no-cache'},timeout=55)
  if not r.ok:raise ValueError('WB read HTTP '+str(r.status_code))
  return r.json()
 try:
  out['campaigns']=req('/api/advert/v2/adverts',dict(ids=','.join(map(str,ids))))['adverts'];out['campaigns_observed_at']=datetime.now(timezone.utc).isoformat();save()
  out['stats']=req('/adv/v3/fullstats',dict(ids=','.join(map(str,ids)),beginDate='2026-11-25',endDate='2026-11-25'));out['stats_observed_at']=datetime.now(timezone.utc).isoformat();out['missing_stats_ids']=sorted(set(ids)-{s['advertId']for s in out['stats']});out['status']='complete';save();print(json.dumps(dict(status=out['status'],returned=len(out['stats']),missing=out['missing_stats_ids'],writes=0)))
 except Exception as e:out.update(status='partial',reason=str(e)if isinstance(e,ValueError)else type(e).__name__);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()