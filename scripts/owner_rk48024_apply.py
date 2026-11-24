import os,json,time,copy,requests
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_rk48024:2026-11-24:v1';CID=41055480
STANDARD='china_agent:daily_ad_execution:v2:daily-2026-11-24-drr-0-buttons-a45a5e28d2f801981c104bbd-5122667182'
REMOVE={1473243443,1473242577,1473245509,1473245508,1473242585}
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a and a['status']=='approved'and a['cid']==CID and a['amount_cny']==1050 and set(a['remove'])==REMOVE
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 assert (io.get(STANDARD)or{}).get('status')=='done','Standard executor still active; no overlap'
 e=io.get(ROOT+':execution')
 if e:print(json.dumps({'status':e['status'],'note':'Existing journal; no mutations replayed'}));return
 e=dict(status='preflight',started_at=now(),ops={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',e)
 orig=requests.sessions.Session.request;allowed=None
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path+('?' + u.query if u.query else '')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v1/balance','/api/advert/v1/config'))or(m=='POST'and u.path=='/api/advert/v2/budget'and kw.get('json')=={'advertIds':[CID]})or allowed==(m,path,kw.get('json'))
  else:ok=False
  assert ok,'Outside exact owner campaign scope';return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()if r.content else{}
 def camp():
  rows=req('/api/advert/v2/adverts?ids='+str(CID)+'&owner_read='+str(time.time_ns()))['adverts'];assert len(rows)==1 and rows[0]['id']==CID;return rows[0]
 def budget():
  rows=req('/api/advert/v2/budget','POST',{'advertIds':[CID]})['adverts'];assert len(rows)==1 and rows[0]['advertId']==CID and rows[0]['currency']=='CNY';return rows[0]['total']
 def verify(expected):
  for _ in range(8):
   c=camp()
   if norm(c)==norm(expected):
    c2=camp()
    if norm(c2)==norm(expected):return c2
   time.sleep(2)
  raise RuntimeError('Whole campaign readback mismatch; no next action')
 def write(name,path,method,body=None):
  nonlocal allowed
  assert (io.get(STANDARD)or{}).get('status')=='done','Standard executor not complete'
  assert name not in e['ops'];e['ops'][name]=dict(status='submitting',submitted_at=now(),method=method,path=path,body=body);save();allowed=(method,path,body)
  try:e['ops'][name]['response']=req(path,method,body)
  finally:allowed=None
  e['wb_writes']+=1;e['ops'][name]['status']='accepted';save()
 try:
  before=camp();bal=budget();e.update(before=before,before_budget=bal);save()
  assert before['status']in(9,11)and before['currency']=='CNY'and before['settings']['placements']=={'search':False,'recommendations':True}
  expected_before=a['expected_before'];assert norm(before)==norm(expected_before),'Composition/bids/state changed since approved proposal; stop'
  assert bal<=2,'New funding detected since zero-balance proposal; do not duplicate'
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['minTopUp']<=105000
  cash=req('/adv/v1/balance');assert cash['currency']=='CNY';typ=0 if cash.get('balance',0)>=1050 else 1 if cash.get('net',0)>=1050 else None;assert typ is not None,'Insufficient cash'
  expected=copy.deepcopy(before);present=REMOVE&{x['nm_id']for x in before['nm_settings']};expected['nm_settings']=[n for n in before['nm_settings']if n['nm_id']not in REMOVE];assert len(expected['nm_settings'])==45
  if present:
   write('exclude','/adv/v0/auction/nms','PATCH',{'nms':[{'advert_id':CID,'nms':{'add':[],'delete':sorted(present)}}]});after=verify(expected);e['ops']['exclude']['status']='verified';e['ops']['exclude']['verified_at']=now();e['after_exclusion']=after;save()
  else:after=verify(expected)
  assert norm(camp())==norm(expected);bal=budget();assert bal<=2,'Funding changed during exclusions; stop'
  write('deposit','/adv/v1/budget/deposit?id='+str(CID),'POST',{'sum':1050,'type':typ});funded=budget();assert funded>=bal+1048,'Deposit not confirmed';verify(expected);e['ops']['deposit'].update(status='verified',verified_at=now(),before_budget=bal,after_budget=funded);save()
  if expected['status']==11:
   write('start','/adv/v0/start?id='+str(CID),'GET');expected['status']=9;after=verify(expected);e['ops']['start'].update(status='verified',verified_at=now());save()
  after=verify(expected);e.update(status='verified',after=after,after_budget=budget(),verified_at=now(),removed=sorted(present),remaining_count=len(after['nm_settings']));save()
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=ROOT+':execution';io.put('china_agent:verified_campaign_state:v1',registry)
  io.create(ROOT+':funding:'+str(CID),dict(id='fund:'+str(CID),cid=CID,status='verified',amount_cny=1050,verified_at=e['ops']['deposit']['verified_at'],steps={'deposit':e['ops']['deposit']},execution_key=ROOT+':execution'))
  io.create('china_agent:experience:v1:owner-rk48024',dict(status='verified',started_at=e['verified_at'],execution_key=ROOT+':execution',action=dict(kind='composition_change',campaign_id=CID,nm_ids=sorted(REMOVE),before=sorted(x['nm_id']for x in before['nm_settings']),after=sorted(x['nm_id']for x in after['nm_settings']))))
  t=io.get('china_agent:new_ad_tests:tracking:v1')or{'plans':{}};day=datetime.now(ZoneInfo('Europe/Moscow')).date();t.setdefault('plans',{})['owner-rk48024']=dict(status='active',campaign_ids=[CID],nm_ids=sorted(n['nm_id']for n in after['nm_settings']),started_at=e['verified_at'],execution_key=ROOT+':execution',auto_topup=False,existing_reports=True,evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))))
  io.put('china_agent:new_ad_tests:tracking:v1',t);e['reports_registered']=True;save()
 except Exception as ex:
  e['status']='uncertain'if any(x['status']in('submitting','accepted')for x in e['ops'].values())else'blocked_after_verified_steps'if e['wb_writes']else'blocked';e['error']=type(ex).__name__+': '+str(ex)[:300];save();raise
 print(json.dumps({k:e.get(k)for k in('status','removed','remaining_count','before_budget','after_budget','wb_writes','reports_registered')}))
if __name__=='__main__':main()

