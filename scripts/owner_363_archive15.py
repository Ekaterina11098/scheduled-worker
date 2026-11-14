"""Archive only41296363 after verified transfer. No funds/start/TG/model calls."""
import json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_363_archive:2026-11-15:v1';CID=41296363
def main():
 io=AdvertisingIO();a=io.get(ROOT+':authorization')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['scope']==dict(campaign_id=CID,action='archive',telegram_send=False,other_actions=False)
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 if io.get(ROOT+':execution'):return
 e=dict(status='preflight',kind='archive_campaign',campaign_id=CID,authorization_key=ROOT+':authorization',wb_writes=0,telegram_calls=0,model_calls=0,telegram_delivery_suppressed_by_owner=True)
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 old=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname=='advert-api.wildberries.ru':
   allowed=(m=='GET'and u.path=='/api/advert/v2/adverts')or(m=='POST'and u.path=='/api/advert/v2/budget')or(m=='GET'and u.path=='/adv/v0/stop'and parse_qs(u.query)=={'id':[str(CID)]})
   assert allowed,'Only archive41296363 permitted'
  elif not url.startswith(io.url+'/rest/v1/'):raise ValueError('No Telegram/model/other service calls')
  return old(session,method,url,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.5);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50)
  if not r.ok:raise RuntimeError('WB HTTP '+str(r.status_code))
  return r.json()if r.content else{}
 def campaigns():return {c['id']:c for c in req('/api/advert/v2/adverts?ids=41296363,41270309')['adverts']}
 def keyed(c):return {n['nm_id']:n for n in c['nm_settings']}
 try:
  validate_identity(Cache(),WB())
  transfer=io.get('china_agent:owner_363_transfer_apply:2026-11-15:v1:execution');assert transfer['status']=='verified'
  ids={n['nm_id']for n in transfer['after_target']['nm_settings']}-{n['nm_id']for n in transfer['before_target']['nm_settings']};assert len(ids)==10
  cs=campaigns();before=cs[CID];target=cs[41270309]
  assert before['currency']=='CNY'and before['status']in(7,11)and len(before['nm_settings'])==17 and not(ids&set(keyed(before)))
  assert target['status']==9 and all(keyed(target)[nm]['bids_kopecks']['recommendations']==28 for nm in ids)
  cash=req('/api/advert/v2/budget','POST',dict(advertIds=[CID]))['adverts'];assert len(cash)==1 and cash[0]['currency']=='CNY'and cash[0]['total']==0
  e.update(before=before,before_budget=0,verified_transfer_key='china_agent:owner_363_transfer_apply:2026-11-15:v1:execution',history_source_keys=['china_agent:owner_363_review:2026-11-15:v1','china_agent:advertising_source:2026-11-14:v2'],target_before=target);save()
  if before['status']!=7:
   e.update(status='submitting',request=dict(path='/adv/v0/stop?id='+str(CID),method='GET'),submitted_at=datetime.now(timezone.utc).isoformat());save()
   try:e['response']=req('/adv/v0/stop?id='+str(CID));e.update(status='accepted',wb_writes=1);save()
   except Exception:e.update(status='uncertain');save();raise
  else:e['already_done']=True
  for _ in range(12):
   now=campaigns();after=now[CID]
   if after['status']==7 and after['settings']==before['settings']and keyed(after)==keyed(before)and now[41270309]['status']==9 and keyed(now[41270309])==keyed(target):
    e.update(status='verified',after=after,target_after=now[41270309],verified_at=datetime.now(timezone.utc).isoformat());save();break
   time.sleep(5)
  assert e['status']=='verified','Archive not verified; no blind repeat'
  reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[str(CID)]=ROOT+':execution';io.put('china_agent:verified_campaign_state:v1',reg)
  print(json.dumps(dict(status=e['status'],campaign_id=CID,after_status=e['after']['status'],wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:
  if e['status']in('submitting','accepted'):e['status']='uncertain'
  elif e['status']not in('uncertain','verified'):e['status']='blocked'
  e['error']=type(ex).__name__+': '+str(ex);save();raise
if __name__=='__main__':main()
