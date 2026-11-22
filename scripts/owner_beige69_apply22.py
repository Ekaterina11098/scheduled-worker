import copy,json,time,requests,os
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_beige69_apply:2026-11-22:v1';CID=42022679;NM=2215883910
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):return {k:sorted(c[k],key=lambda n:n['nm_id'])if k=='nm_settings'else c[k]for k in('id','status','currency','settings','bid_type','nm_settings')}
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a['status']=='approved'and a['owner_id']==5122667182 and a['nm_id']==NM and a['target_minor']==69
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 e=io.get(ROOT+':execution')
 if e and e['status']=='verified':print('Verified already, no repeat');return
 if e:assert 'operation'not in e,'Uncertain operation not replayed'
 else:e=dict(status='preflight',created_at=now(),wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 orig=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path=='/api/advert/v2/adverts'or m=='POST'and u.path=='/api/advert/v1/bids/min'or allowed is not None and(m,u.path,kw.get('json'))==allowed
  else:ok=False
  assert ok,'Outside exact bid scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def read():
  time.sleep(1.3);r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':str(CID),'owner_read':time.time_ns()},headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store','Pragma':'no-cache'},timeout=(10,55));r.raise_for_status();c=r.json()['adverts'];assert len(c)==1 and c[0]['id']==CID;return c[0]
 try:
  before=read();assert before['status']==9 and before['currency']=='CNY'and before['settings']['payment_type']=='cpc'and before['settings']['placements']=={'search':False,'recommendations':True}
  assert {n['nm_id']for n in before['nm_settings']}=={NM},'6/7 must remain excluded'
  old=before['nm_settings'][0]['bids_kopecks']['recommendations'];assert old in(40,69),'Unreviewed current bid'
  r=requests.post('https://advert-api.wildberries.ru/api/advert/v1/bids/min',headers={'Authorization':io.token},json=dict(advert_id=CID,nm_ids=[NM],payment_type='cpc',placement_types=['recommendation']),timeout=(10,50));r.raise_for_status();q=r.json();floor=next(b['value']for x in q['bids']if x['nm_id']==NM for b in x['bids']if b['type']=='recommendation'and b['currency']=='CNY');assert floor<=69
  e.update(before=before,minimum=q);expected=copy.deepcopy(before);expected['nm_settings'][0]['bids_kopecks']['recommendations']=69;save()
  if old!=69:
   body=dict(bids=[dict(advert_id=CID,nm_bids=[dict(nm_id=NM,bid_kopecks=69,placement='recommendations')])]);e['operation']=dict(status='submitting',submitted_at=now(),body=body);save();allowed=('PATCH','/api/advert/v1/bids',body)
   try:
    r=requests.patch('https://advert-api.wildberries.ru/api/advert/v1/bids',headers={'Authorization':io.token},json=body,timeout=(10,55));e['operation'].update(http_status=r.status_code,response=r.text[:800]);r.raise_for_status();e['operation']['status']='accepted';e['wb_writes']=1;save()
   except Exception:e['operation']['status']='uncertain';save();raise
   finally:allowed=None
  streak=[]
  for _ in range(18):
   c=read();e['last_read']=c;save();streak=streak+[c]if norm(c)==norm(expected)else[]
   if len(streak)==3:break
   time.sleep(3)
  assert len(streak)==3,'WB state uncertain; never repeat bid blindly'
  e.update(status='verified',after=streak[-1],readbacks=streak,verified_at=now(),already_done=old==69)
  if 'operation'in e:e['operation']['status']='verified'
  save();key=ROOT+':campaign:'+str(CID);value=dict(e,id=CID,cid=CID)
  if io.get(key):io.put(key,value)
  else:assert io.create(key,value)
  reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[str(CID)]=key;io.put('china_agent:verified_campaign_state:v1',reg)
  if old!=69:io.create('china_agent:experience:v1:owner-beige69-22',dict(status='verified',started_at=e['verified_at'],execution_key=key,action=dict(kind='bid_change',campaign_id=CID,nm_ids=[NM],before=old,after=69),before=before,after=e['after']))
  day=datetime.now(ZoneInfo('Europe/Moscow')).date();t=io.get('china_agent:new_ad_tests:tracking:v1');t.setdefault('plans',{})['owner-beige69-22']=dict(status='active',campaign_ids=[CID],nm_ids=[NM],started_at=e['verified_at'],bid_minor=69,placement='recommendations',execution_key=key,auto_topup=False,existing_reports=True,evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))));io.put('china_agent:new_ad_tests:tracking:v1',t);e['reports_registered']=True;save()
  print(json.dumps(dict(status=e['status'],bid_cny=.69,wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:e.update(status='attention_required',error=type(ex).__name__+': '+str(ex)[:250]);save();raise
 finally:requests.sessions.Session.request=orig
if __name__=='__main__':main()

