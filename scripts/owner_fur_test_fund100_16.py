"""One explicit owner-approved 100 CNY deposit. No bids, starts, Telegram or model calls."""
import os,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_fur_test_fund100:2026-11-16:v1'
CID=41925305
IDS={2216217906,2216257724,2216045897,2215883910,2216111729,2216167898}
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();a=c.get(ROOT+':authorization')or{}
 assert a.get('status')=='approved' and a.get('owner_id')==5122667182 and a.get('campaign_id')==CID and a.get('amount_cny')==100
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 key=ROOT+':execution'
 if c.get(key):print('Execution already journalled: no repeat');return
 e=dict(status='preflight',campaign_id=CID,kind='topup_campaign',amount_cny=100,authorization_key=ROOT+':authorization',wb_writes=0,telegram_calls=0,model_calls=0,created_at=stamp())
 assert c.create(key,e),'Concurrent funding request'
 def save():c.put(key,json.loads(json.dumps(e)))
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname=='advert-api.wildberries.ru':
   safe=(m=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance'))or(m=='POST'and u.path=='/api/advert/v2/budget')
   exact=(m=='POST'and u.path=='/adv/v1/budget/deposit'and parse_qs(u.query)=={'id':[str(CID)]}and kw.get('json')==dict(sum=100,type=e.get('wallet_type')))
   assert safe or exact,'Outside exact funding scope'
  else:assert u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and u.path.startswith('/rest/v1/'),'No Telegram/model/unrelated calls'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.5)
  r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':os.environ['WB_TOKEN_3']},json=body,timeout=45)
  if not r.ok:raise RuntimeError('WB HTTP '+str(r.status_code))
  return r.json()if r.content else{}
 def campaign():
  rows=req('/api/advert/v2/adverts?ids='+str(CID))['adverts'];assert len(rows)==1
  x=rows[0];assert x['id']==CID and x['currency']=='CNY' and x['settings']['name']=='Шубы — поиск — тест'
  assert x['settings']['placements']==dict(search=True,recommendations=False)and x['settings']['payment_type']=='cpc'
  assert len(x['nm_settings'])==6 and {n['nm_id']for n in x['nm_settings']}==IDS
  assert all(n['subject']['id']==4377 and n['bids_kopecks']['search']==41 and n['bids_kopecks'].get('recommendations',0)==0 for n in x['nm_settings'])
  return x
 def budget():
  rows=req('/api/advert/v2/budget','POST',dict(advertIds=[CID]))['adverts'];assert len(rows)==1 and rows[0]['advertId']==CID and rows[0]['currency']=='CNY'
  return rows[0]['total']
 try:
  validate_identity(c,WB())
  canonical=c.get('china_agent:owner_fur_search:2026-11-16:v1:campaign:'+str(CID))
  assert canonical['status']=='verified' and canonical['after']['id']==CID
  before=campaign();assert before['status']in(9,11)
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY' and cfg['minTopUp']<=10000
  funds=req('/adv/v1/balance');assert funds['currency']=='CNY'
  e['wallet_type']=1 if funds.get('net',0)>=100 else 0 if funds.get('balance',0)>=100 else None
  assert e['wallet_type']is not None,'Insufficient available wallet'
  e.update(before=before,before_budget=budget(),wallet_before=funds,config=cfg,launch_execution_key='china_agent:owner_fur_search:2026-11-16:v1:campaign:'+str(CID));save()
  assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
  e.update(status='submitting',submitted_at=stamp(),request=dict(path='/adv/v1/budget/deposit?id='+str(CID),method='POST',body=dict(sum=100,type=e['wallet_type'])));save()
  try:e['response']=req(e['request']['path'],'POST',e['request']['body']);e.update(status='accepted',wb_writes=1);save()
  except Exception:e.update(status='uncertain');save();raise
  for i in range(10):
   cash=budget();after=campaign();e.update(after_budget=cash,after=after);save()
   assert after['settings']==before['settings'] and sorted(after['nm_settings'],key=lambda n:n['nm_id'])==sorted(before['nm_settings'],key=lambda n:n['nm_id']),'Composition/bids changed'
   if e['before_budget']+98<=cash<=e['before_budget']+100:
    e.update(status='verified',verified_at=stamp());save();break
   time.sleep(4)
  assert e['status']=='verified','Funding not verified; never repeat deposit'
  registry=c.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=key;c.put('china_agent:verified_campaign_state:v1',registry)
  print(json.dumps(dict(status=e['status'],campaign_id=CID,amount_cny=100,before_budget=e['before_budget'],after_budget=e['after_budget'],campaign_status=e['after']['status'],wb_writes=1,telegram_calls=0)))
 except Exception as ex:
  if e['status']in('submitting','accepted'):e['status']='uncertain'
  elif e['status']not in('verified','uncertain'):e['status']='blocked'
  e['error']=type(ex).__name__+': '+str(ex);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
