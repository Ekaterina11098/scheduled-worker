import copy,json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_fur67_remove:2026-11-22:v1';CID=42022679;REMOVE={2216111729,2216167898};KEEP=2215883910
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):return {k:sorted(c[k],key=lambda n:n['nm_id'])if k=='nm_settings'else c[k]for k in('id','status','currency','settings','bid_type','nm_settings')}
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a['status']=='approved'and a['owner_id']==5122667182 and a['campaign_id']==CID and set(a['remove'])==REMOVE
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 e=io.get(ROOT+':execution')
 if e and e['status']=='verified':print('Already verified, no writes');return
 if e:assert 'operation'not in e,'Existing uncertain operation must not replay'
 else:e=dict(status='preflight',created_at=now(),wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 orig=requests.sessions.Session.request;allow=None
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path=='/api/advert/v2/adverts'or allow is not None and(m,u.path,kw.get('json'))==allow
  else:ok=False
  assert ok,'Outside exact owner scope';return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def read():
  time.sleep(1.3);r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':str(CID),'owner_read':time.time_ns()},headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store','Pragma':'no-cache'},timeout=(10,55));r.raise_for_status();rows=r.json()['adverts'];assert len(rows)==1 and rows[0]['id']==CID;return rows[0]
 try:
  before=read();members={n['nm_id']:n for n in before['nm_settings']};assert KEEP in members and before['currency']=='CNY'and before['status']==9 and before['settings']['placements']=={'search':False,'recommendations':True}
  e['before']=before;e['beige_bid_before']=members[KEEP]['bids_kopecks'];expected=copy.deepcopy(before);expected['nm_settings']=[n for n in before['nm_settings']if n['nm_id']not in REMOVE];missing=sorted(REMOVE&set(members));save()
  if missing:
   body={'nms':[{'advert_id':CID,'nms':{'add':[],'delete':missing}}]};e['operation']=dict(status='submitting',body=body,submitted_at=now());save();allow=('PATCH','/adv/v0/auction/nms',body)
   try:
    r=requests.patch('https://advert-api.wildberries.ru/adv/v0/auction/nms',headers={'Authorization':io.token},json=body,timeout=(10,55));e['operation']['http_status']=r.status_code;e['operation']['response']=r.text[:1000];r.raise_for_status();e['operation']['status']='accepted';e['wb_writes']=1;save()
   except Exception:e['operation']['status']='uncertain';save();raise
   finally:allow=None
  streak=[]
  for _ in range(18):
   current=read();e['last_read']=current;save()
   if norm(current)==norm(expected):streak.append(current)
   else:streak=[]
   if len(streak)==3:break
   time.sleep(3)
  assert len(streak)==3,'WB readback inconsistent; do not repeat removal'
  e.update(status='verified',after=streak[-1],readbacks=streak,verified_at=now(),reports_registered=True);e.get('operation',{})['status']='verified';save()
  receipt=dict(e,id=CID,cid=CID);key=ROOT+':campaign:'+str(CID)
  if io.get(key):io.put(key,receipt)
  else:assert io.create(key,receipt)
  reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[str(CID)]=key;io.put('china_agent:verified_campaign_state:v1',reg)
  io.create('china_agent:experience:v1:owner-fur67-remove22',dict(status='verified',started_at=e['verified_at'],execution_key=key,action=dict(kind='exclude',campaign_id=CID,nm_ids=missing),before=before,after=e['after']))
  print(json.dumps(dict(status='verified',remaining=[n['nm_id']for n in e['after']['nm_settings']],beige_bid=e['beige_bid_before'],wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:e.update(status='attention_required',error=type(ex).__name__+': '+str(ex)[:250]);save();raise
 finally:requests.sessions.Session.request=orig
if __name__=='__main__':main()

