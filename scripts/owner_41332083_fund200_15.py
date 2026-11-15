"""Exact owner200CNY deposit only41332083. No Telegram or other marketplace changes."""
import json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_41332083_fund200:2026-11-15:v1';CID=41332083
def keyed(c):return{n['nm_id']:n for n in c['nm_settings']}
def main():
 io=AdvertisingIO();a=io.get(ROOT+':authorization')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['scope']==dict(campaign_id=CID,amount_cny=200,telegram_send=False,other_actions=False)
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 if io.get(ROOT+':execution'):return
 e=dict(status='preflight',kind='topup_campaign',campaign_id=CID,amount_cny=200,authorization_key=ROOT+':authorization',wb_writes=0,telegram_calls=0,model_calls=0,telegram_delivery_suppressed_by_owner=True)
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname=='advert-api.wildberries.ru':
   allowed=(m=='GET'and u.path in ['/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance'])or(m=='POST'and u.path=='/api/advert/v2/budget')
   if u.path=='/adv/v1/budget/deposit':allowed=m=='POST'and parse_qs(u.query)=={'id':[str(CID)]}and kw.get('json')==dict(sum=200,type=e.get('wallet_type'))
   assert allowed,'Only exact deposit200 permitted'
  elif not url.startswith(io.url+'/rest/v1/'):raise ValueError('No Telegram/model/unrelated calls')
  return original(session,method,url,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.5);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50)
  if not r.ok:raise RuntimeError('WB HTTP '+str(r.status_code))
  return r.json()if r.content else{}
 def campaign():
  r=req('/api/advert/v2/adverts?ids='+str(CID))['adverts'];assert len(r)==1 and r[0]['id']==CID and r[0]['currency']=='CNY';return r[0]
 def budget():
  r=req('/api/advert/v2/budget','POST',dict(advertIds=[CID]))['adverts'];assert len(r)==1 and r[0]['advertId']==CID and r[0]['currency']=='CNY';return r[0]['total']
 try:
  validate_identity(Cache(),WB())
  proposal=io.get('china_agent:owner_41332083_continuation:2026-11-15:v1:proposal');assert proposal['amount_cny']==200
  audit=io.get('china_agent:owner_final_audit330:2026-11-15:v1');assert all(r['matches']for r in audit['items'])
  before=campaign();assert before['status']==9 and before['settings']['payment_type']=='cpc'and before['settings']['placements']==dict(search=True,recommendations=False)
  assert keyed(before)==keyed(audit['campaigns'][str(CID)]),'Composition/bids changed since owner proposal'
  assert 1473244000 not in keyed(before)and keyed(before)[1473245506]['bids_kopecks']['search']==28
  assert str(CID)not in(io.get('china_agent:budget_owner_policy:v1')or{}).get('do_not_fund',{})
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['minTopUp']<=20000
  wallet=req('/adv/v1/balance');assert wallet['currency']=='CNY'
  e['wallet_type']=0 if wallet.get('balance',0)>=200 else 1 if wallet.get('net',0)>=200 else None
  assert e['wallet_type']is not None,'Insufficient available CNY wallet'
  e.update(before=before,before_budget=budget(),config=cfg,proposal_key='china_agent:owner_41332083_continuation:2026-11-15:v1:proposal');save()
  e.update(status='submitting',submitted_at=datetime.now(timezone.utc).isoformat(),request=dict(path='/adv/v1/budget/deposit?id='+str(CID),method='POST',body=dict(sum=200,type=e['wallet_type'])));save()
  try:e['response']=req(e['request']['path'],'POST',e['request']['body']);e.update(status='accepted',wb_writes=1);save()
  except Exception:e['status']='uncertain';save();raise
  for _ in range(12):
   cash=budget();after=campaign()
   if e['before_budget']+198<=cash<=e['before_budget']+200 and after['status']==9 and after['settings']==before['settings']and keyed(after)==keyed(before):
    e.update(status='verified',after=after,after_budget=cash,verified_at=datetime.now(timezone.utc).isoformat());save();break
   time.sleep(5)
  assert e['status']=='verified','Deposit not yet verified; never replay'
  reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[str(CID)]=ROOT+':execution';io.put('china_agent:verified_campaign_state:v1',reg)
  proposal.update(status='executed_verified',execution_key=ROOT+':execution',verified_at=e['verified_at']);io.put(e['proposal_key'],proposal)
  print(json.dumps(dict(status=e['status'],before=e['before_budget'],after=e['after_budget'],amount=200,wb_writes=1,telegram_calls=0)))
 except Exception as ex:
  if e['status']in('submitting','accepted'):e['status']='uncertain'
  elif e['status']not in('verified','uncertain'):e['status']='blocked'
  e['error']=type(ex).__name__+': '+str(ex);save();raise
if __name__=='__main__':main()
