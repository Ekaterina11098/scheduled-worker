import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from owner_rk48024_apply import ROOT,CID,STANDARD,REMOVE,norm,now
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');e=io.get(ROOT+':execution');ui=io.get(ROOT+':exclusion_ui_verified')
 assert a['status']=='approved' and a['amount_cny']==1050 and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 assert e['wb_writes']==1 and e['ops']['exclude']['status']=='accepted'
 assert not any(k in e['ops'] for k in ('deposit','start')),'Existing operation; never replay'
 assert ui['status']=='verified' and ui['id']==CID and ui['remaining_count']==45
 expected=copy.deepcopy(e['before']);expected['nm_settings']=[n for n in expected['nm_settings'] if n['nm_id']not in REMOVE]
 assert sorted(ui['nm_settings'],key=lambda n:n['nm_id'])==norm(expected)['nm_settings']
 assert (datetime.now(timezone.utc)-datetime.fromisoformat(ui['observed_at'].replace('Z','+00:00'))).total_seconds()<900
 assert io.create(ROOT+':continuation_claim',dict(status='claimed',at=now())),'Continuation already claimed'
 orig=requests.sessions.Session.request;allowed=None
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path+('?' +u.query if u.query else '')
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH') and u.path.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and((m=='GET'and u.path in('/api/advert/v2/adverts','/adv/v1/balance','/api/advert/v1/config'))or(m=='POST'and u.path=='/api/advert/v2/budget'and kw.get('json')=={'advertIds':[CID]})or allowed==(m,path,kw.get('json'))))
  assert ok,'Outside exact funding/resume scope';return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def save():io.put(ROOT+':execution',e)
 def req(path,method='GET',body=None):
  time.sleep(1.4);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()if r.content else{}
 def camp():
  c=req('/api/advert/v2/adverts?ids='+str(CID)+'&owner_read='+str(time.time_ns()))['adverts'];assert len(c)==1 and c[0]['id']==CID;return c[0]
 def budget():
  b=req('/api/advert/v2/budget','POST',{'advertIds':[CID]})['adverts'];assert len(b)==1 and b[0]['advertId']==CID and b[0]['currency']=='CNY';return b[0]['total']
 def write(name,path,method,body=None):
  nonlocal allowed
  assert (io.get(STANDARD)or{}).get('status')=='done'
  assert name not in e['ops'];e['ops'][name]=dict(status='submitting',submitted_at=now(),method=method,path=path,body=body);save();allowed=(method,path,body)
  try:e['ops'][name]['response']=req(path,method,body)
  finally:allowed=None
  e['wb_writes']+=1;e['ops'][name]['status']='accepted';save()
 try:
  c=camp();assert norm(c)in(norm(e['before']),norm(expected)),'Unrelated composition/bid/state change'
  bal=budget();assert bal==0,'Balance changed; do not duplicate funding'
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['minTopUp']<=105000
  cash=req('/adv/v1/balance');assert cash['currency']=='CNY';typ=0 if cash.get('balance',0)>=1050 else 1 if cash.get('net',0)>=1050 else None;assert typ is not None
  e['prior_api_error']=e.pop('error',None);e['ops']['exclude'].update(status='verified',verified_at=ui['observed_at'],verification_source=ROOT+':exclusion_ui_verified')
  e['after_exclusion']=expected;e['status']='continuing';save()
  write('deposit','/adv/v1/budget/deposit?id='+str(CID),'POST',{'sum':1050,'type':typ})
  funded=budget();assert funded>=1048,'Funding result uncertain; no replay'
  e['ops']['deposit'].update(status='verified',verified_at=now(),before_budget=bal,after_budget=funded);save()
  c=camp();assert norm(c)in(norm(e['before']),norm(expected)),'State changed after funding'
  write('start','/adv/v0/start?id='+str(CID),'GET')
  c=camp();e.update(status='awaiting_final_ui_verification',api_after=c,after_budget=budget(),finished_writes_at=now());save()
 except Exception as ex:
  e.update(status='uncertain',error=type(ex).__name__+': '+str(ex)[:300]);save();raise
 print(json.dumps({'status':e['status'],'wb_writes':e['wb_writes'],'after_budget':e.get('after_budget'),'api_status':c['status'],'api_count':len(c['nm_settings'])}))
if __name__=='__main__':main()
