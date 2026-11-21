"""Read-only reconcile gray6 addition; never repeat membership/bid mutation."""
import copy,time,json,requests
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_fur6_return:2026-11-21:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();e=io.get(ROOT+':execution');s=e['groups'][0]
 assert e['wb_writes']==1 and s['steps']['add']['status']=='verified'
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url)
  if (u.hostname or'').endswith('wildberries.ru'):assert method.upper()=='GET'and u.path=='/api/advert/v2/adverts','No WB mutations'
  if 'telegram'in(u.hostname or'')or'openai'in(u.hostname or''):raise ValueError('No TG/model')
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 expected=copy.deepcopy(s['before']);expected['nm_settings'].append(next(n for n in s['steps']['add']['after']['nm_settings']if n['nm_id']==2216111729))
 def normalized(c):return {k:(sorted(c[k],key=lambda n:n['nm_id'])if k=='nm_settings'else c[k])for k in('id','status','currency','settings','bid_type','nm_settings')}
 consecutive=[];audit=[]
 for attempt in range(6):
  if attempt:time.sleep(10)
  r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':42022679,'_owner_read_nonce':str(time.time_ns())},headers={'Authorization':io.token,'Cache-Control':'no-cache, no-store','Pragma':'no-cache'},timeout=40);r.raise_for_status();c=r.json()['adverts'][0]
  audit.append(dict(at=now(),campaign=c))
  if normalized(c)==normalized(expected):consecutive.append(c)
  else:consecutive=[]
  if len(consecutive)==3:break
 e['reconciliation_reads']=audit
 if len(consecutive)!=3:
  e.update(status='uncertain',error='Three stable exact reads not obtained');io.put(ROOT+':execution',e);raise ValueError(e['error'])
 s.update(status='verified',after=consecutive[-1],readbacks=consecutive,verified_at=now())
 e.update(status='verified',verified_at=now(),added_count=1,package_readback=consecutive,error=None)
 child=ROOT+':campaign:42022679'
 io.put(child,s)if io.get(child)else io.create(child,s)
 registry=io.get('china_agent:verified_campaign_state:v1')or{};registry['42022679']=child;io.put('china_agent:verified_campaign_state:v1',registry)
 tracking=io.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={});day=datetime.now(ZoneInfo('Europe/Moscow')).date()
 tracking.setdefault('plans',{})['owner-fur6-return-20261121-42022679']=dict(status='active',campaign_ids=[42022679],started_at=s['verified_at'],execution_key=child,owner_approved_small_sample_risk=True,existing_reports=True,auto_topup=False,nm_ids=[2216111729],bid_minor=38,placement='recommendations',evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))))
 io.put('china_agent:new_ad_tests:tracking:v1',tracking);e['reports_registered']=True;io.put(ROOT+':execution',e)
 print(json.dumps(dict(status='verified',wb_writes=0,original_addition_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()
