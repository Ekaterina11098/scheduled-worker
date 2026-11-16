"""Exact owner-approved six-fur search launch; durable single-attempt mutations."""
import os,json,time
from datetime import datetime,timezone
import requests
from china_cloud_cost_control import Cache,stamp
from china_new_ads import Transport
ROOT='china_agent:owner_fur_search:2026-11-16:v1:'
IDS={2216217906,2216257724,2216045897,2215883910,2216111729,2216167898}
def check(c,bids=False,active=False):
 assert c['currency']=='CNY' and c['bid_type']=='manual'
 assert c['settings']['name']=='Шубы — поиск — тест' and c['settings']['payment_type']=='cpc'
 assert c['settings']['placements']==dict(search=True,recommendations=False)
 assert len(c['nm_settings'])==6 and {n['nm_id'] for n in c['nm_settings']}==IDS
 assert all(n['subject']['id']==4377 for n in c['nm_settings'])
 if bids:assert all(n['bids_kopecks']['search']==41 and n['bids_kopecks'].get('recommendations',0)==0 for n in c['nm_settings'])
 assert c['status']==(9 if active else 4)
 return c
def main():
 db=Cache();a=db.get(ROOT+'approval');ref=db.get(ROOT+'read')
 assert a['status']=='approved' and a['owner_id']==5122667182 and set(a['nm_ids'])==IDS
 assert a['bid_minor']==41 and a['funding_cny']==100 and a['placement']=='search' and a['no_daily_limits'] is True
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))
 e=dict(status='running',steps={},created_at=stamp(),approval_key=ROOT+'approval',wb_writes=0)
 if not db.create(ROOT+'execution',e):raise RuntimeError('Existing execution: inspect, never replay')
 io=type('ReadIO',(),dict(token=os.environ['WB_TOKEN_3']))();t=Transport(io)
 def save():db.put(ROOT+'execution',e)
 def req(path,method='GET',body=None):
  if path=='/adv/v1/balance':
   r=requests.get('https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},timeout=45)
   if not r.ok:raise RuntimeError('Account read HTTP '+str(r.status_code))
   return r.json()
  return t.request(path,method,body)
 def write(step,path,method,body=None):
  assert step not in e['steps'],'Never repeat mutation'
  assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))
  e['steps'][step]=dict(status='submitting',method=method,path=path,body=body,at=stamp());save()
  try:r=req(path,method,body)
  except Exception:
   e['steps'][step]['status']='uncertain';e['status']='uncertain';save();raise
  e['steps'][step].update(status='accepted',response=r,accepted_at=stamp());e['wb_writes']+=1;save();return r
 def wait(fn):
  for i in range(10):
   try:return fn()
   except (AssertionError,ValueError,RuntimeError):
    if i==9:raise
    time.sleep(8)
 def verified(step,data):e['steps'][step].update(status='verified',readback=data,verified_at=stamp());save()
 try:
  old=t.campaign(41756218);assert old['status']==11;e['old_before']=old;save()
  cfg=t.config();assert cfg['currency']=='CNY' and cfg['minTopUp']<=10000 and 41%cfg['cpcStep']==0 and 41<=cfg['cpcMaxBid']
  account=req('/adv/v1/balance');assert account['currency']=='CNY'
  source=1 if account.get('net',0)>=100 else 0
  assert account.get('net' if source==1 else 'balance',0)>=100,'Insufficient authorized account funds'
  e['account_before']=account;e['config']=cfg;save()
  listing=req('/adv/v1/promotion/count')
  ids=sorted({r['advertId'] for g in listing.get('adverts',[]) for r in g.get('advert_list',[])})
  assert len(ids)<=500
  states=[]
  for i in range(0,len(ids),50):states+=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids[i:i+50]))).get('adverts',[])
  assert not any(c.get('settings',{}).get('name')==a['name'] and c['status']!=7 for c in states),'Existing matching campaign; reconcile'
  assert not any(c['id']!=41756218 and c['status']in(4,9,11) and IDS & {n['nm_id'] for n in c.get('nm_settings',[])} for c in states),'Unexpected duplicate fur campaign'
  assert ref['status']=='complete' and all(n>0 for n in ref['published_stock']['amounts'].values())
  assert datetime.now(timezone.utc)-datetime.fromisoformat(ref['completed_at'])<__import__('datetime').timedelta(hours=1)
  mins=req('/api/advert/v1/bids/min','POST',dict(advert_id=41756218,nm_ids=sorted(IDS),payment_type='cpc',placement_types=['search']))
  values={n['nm_id']:next(b['value'] for b in n['bids'] if b['type']=='search' and b['currency']=='CNY')for n in mins['bids']}
  assert set(values)==IDS and all(0<v<=41 for v in values.values());e['minimums_before']=mins;save()
  r=write('create','/adv/v2/seacat/save-ad','POST',dict(name=a['name'],nms=sorted(IDS),bid_type='manual',payment_type='cpc',placement_types=['search']))
  cid=r if type(r)is int else r.get('advertId') if isinstance(r,dict)else None
  assert type(cid)is int and cid>0
  e['campaign_id']=cid;save();draft=wait(lambda:check(t.campaign(cid)));e['before']=draft;verified('create',draft)
  write('bids','/api/advert/v1/bids','PATCH',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=n,bid_kopecks=41,placement='search')for n in sorted(IDS)])]))
  verified('bids',wait(lambda:check(t.campaign(cid),True)))
  before=t.budget(cid);assert before==0;e['before_budget']=before;save()
  write('funding','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=100,type=source))
  def funded():
   b=t.budget(cid);assert b==100;return b
  e['funded_budget']=wait(funded);verified('funding',e['funded_budget'])
  check(t.campaign(cid),True);assert t.campaign(41756218)['status']==11
  write('start','/adv/v0/start?id='+str(cid),'GET')
  after=wait(lambda:check(t.campaign(cid),True,True));e['after']=after;verified('start',after)
  old=t.campaign(41756218);assert old==e['old_before'],'Old campaign unexpectedly changed'
  e.update(status='verified',old_after=old,after_budget=t.budget(cid),verified_at=stamp());save()
  child=ROOT+'campaign:'+str(cid)
  receipt=dict(status='verified',before=e['before'],after=after,before_budget=0,after_budget=e['after_budget'],funding_cny=100,steps=e['steps'],verified_at=e['verified_at'],authorization_key=ROOT+'approval')
  assert db.create(child,receipt)
  registry=db.get('china_agent:verified_campaign_state:v1')or{}
  registry[str(cid)]=child;db.put('china_agent:verified_campaign_state:v1',registry)
  tracking=db.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={})
  tracking.setdefault('plans',{})['owner-fur-search-20261116']=dict(status='active',campaign_ids=[cid],started_at=e['verified_at'],execution_key=child,budget_cny=100,items=[dict(name=a['name'],payment_type='cpc',bid_type='manual',placements=['search'],budget_cny=100,auto_topup=False,skus=[dict(nm_id=n,bid_minor=41)for n in sorted(IDS)])],existing_reports=True)
  db.put('china_agent:new_ad_tests:tracking:v1',tracking)
 except Exception as ex:
  e.update(status='uncertain' if e.get('status')=='uncertain' or any(s['status']in('submitting','accepted')for s in e['steps'].values()) else 'blocked',reason=str(ex)[:250] or type(ex).__name__);save();raise
 print(json.dumps(dict(status=e['status'],campaign_id=e.get('campaign_id'),wb_writes=e['wb_writes'])))
if __name__=='__main__':main()
