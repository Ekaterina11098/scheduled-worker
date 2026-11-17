"""Exact owner-approved ten-bag search launch; no Telegram, no repeated mutations."""
import os,json,time
from datetime import datetime,timezone
import requests
from china_cloud_cost_control import Cache,stamp,WB,validate_identity
from china_new_ads import Transport
ROOT='china_agent:owner_bags_search:2026-11-17:v1:'
IDS={1473243891,1473243908,1473244339,1473245509,1473244357,1473244358,1473244359,1473245508,1473245497,1473245495}
NAME='МСК · сумки · поиск · тест10 · 17.11'
def check(c,bids=False,active=False):
 assert c['currency']=='CNY' and c['bid_type']=='manual'
 assert c['settings']['name']==NAME and c['settings']['payment_type']=='cpc'
 assert c['settings']['placements']==dict(search=True,recommendations=False)
 assert len(c['nm_settings'])==10 and {n['nm_id'] for n in c['nm_settings']}==IDS
 assert all(n['subject']['id']==50 for n in c['nm_settings'])
 if bids:assert all(n['bids_kopecks']['search']==28 and n['bids_kopecks'].get('recommendations',0)==0 for n in c['nm_settings'])
 assert c['status']==(9 if active else 4)
 return c
def main():
 db=Cache();a=db.get(ROOT+'approval');p=db.get(a['proposal_key'])
 assert a['status']=='approved' and a['owner_id']==5122667182 and set(a['nm_ids'])==IDS
 assert a['bid_minor']==28 and a['funding_cny']==500 and a['placement']=='search' and a['no_daily_limits'] is True
 assert a['telegram_notifications'] is False and a['name']==NAME and {x['nm_id']for x in p['items']}==IDS
 refs=[db.get(k)for k in p['sources']];assert all(x['status']=='complete'for x in refs)
 models={nm:e for x in refs for nm,e in x['economics']['rows'].items()}
 assert all(models[str(n)]['expected_margin_before_ads_cny']>0 and models[str(n)]['stock_free']>0 and models[str(n)]['published_stock']>0 for n in IDS)
 assert all((datetime.now(timezone.utc)-datetime.fromisoformat(x['completed_at'])).total_seconds()<3600 for x in refs)
 validate_identity(db,WB())
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))
 e=dict(status='running',steps={},created_at=stamp(),approval_key=ROOT+'approval',wb_writes=0)
 if not db.create(ROOT+'execution',e):raise RuntimeError('Existing execution: inspect, never replay')
 io=type('ReadIO',(),dict(token=os.environ['WB_TOKEN_3']))();t=Transport(io)
 original_http=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  from urllib.parse import urlparse,parse_qs
  u=urlparse(url);m=method.upper();body=kw.get('json');path=u.path;cid=e.get('campaign_id')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=path.startswith('/rest/v1/') and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':
   ok=(m=='GET'and path in('/api/advert/v1/config','/api/advert/v2/adverts','/adv/v1/promotion/count','/adv/v1/balance'))or(m=='POST'and path in('/api/advert/v1/bids/min','/api/advert/v2/budget'))
   if m=='POST'and path=='/adv/v2/seacat/save-ad':ok=body==dict(name=NAME,nms=sorted(IDS),bid_type='manual',payment_type='cpc',placement_types=['search'])
   if m=='PATCH'and path=='/api/advert/v1/bids':ok=bool(cid)and body==dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=n,bid_kopecks=28,placement='search')for n in sorted(IDS)])])
   if path=='/adv/v1/budget/deposit':ok=m=='POST'and bool(cid)and parse_qs(u.query)=={'id':[str(cid)]}and isinstance(body,dict)and set(body)=={'sum','type'}and body['sum']==500 and body['type']in(0,1)
   if path=='/adv/v0/start':ok=m=='GET'and bool(cid)and parse_qs(u.query)=={'id':[str(cid)]}and e['steps'].get('funding',{}).get('status')=='verified'
  else:ok=False
  assert ok,'Transport outside exact owner-approved scope'
  return original_http(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
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
  cfg=t.config();assert cfg['currency']=='CNY' and cfg['minTopUp']<=50000 and 28%cfg['cpcStep']==0 and 28<=cfg['cpcMaxBid']
  account=req('/adv/v1/balance');assert account['currency']=='CNY'
  source=1 if account.get('net',0)>=500 else 0
  assert account.get('net' if source==1 else 'balance',0)>=500,'Insufficient authorized account funds'
  e['account_before']=account;e['config']=cfg;save()
  listing=req('/adv/v1/promotion/count')
  ids=sorted({r['advertId'] for g in listing.get('adverts',[]) for r in g.get('advert_list',[])})
  assert len(ids)<=500
  states=[]
  for i in range(0,len(ids),50):states+=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids[i:i+50]))).get('adverts',[])
  assert not any(c.get('settings',{}).get('name')==a['name'] and c['status']!=7 for c in states),'Existing matching campaign; reconcile'
  assert not any(c['status']==9 and IDS & {n['nm_id'] for n in c.get('nm_settings',[])} for c in states),'Selected SKU already in an active campaign'
  e['old_fur_observed']=[dict(id=c['id'],status=c['status'],name=c['settings']['name'])for c in states if c['id']==41756218];save()
  reference=next(c for c in states if c['id']==41298169)
  member=next(n['nm_id']for n in reference['nm_settings']if n['subject']['id']==50)
  mins=req('/api/advert/v1/bids/min','POST',dict(advert_id=41298169,nm_ids=[member],payment_type='cpc',placement_types=['search']))
  values=[b['value']for n in mins['bids']for b in n['bids']if b['type']=='search'and b['currency']=='CNY']
  assert len(values)==1 and 0<values[0]<=28;e['minimums_before']=mins;e['preflight_economics']={str(n):models[str(n)]for n in IDS};save()
  r=write('create','/adv/v2/seacat/save-ad','POST',dict(name=a['name'],nms=sorted(IDS),bid_type='manual',payment_type='cpc',placement_types=['search']))
  cid=r if type(r)is int else r.get('advertId') if isinstance(r,dict)else None
  assert type(cid)is int and cid>0
  e['campaign_id']=cid;save();draft=wait(lambda:check(t.campaign(cid)));e['before']=draft;verified('create',draft)
  exact=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=sorted(IDS),payment_type='cpc',placement_types=['search']))
  values={n['nm_id']:next(b['value']for b in n['bids']if b['type']=='search'and b['currency']=='CNY')for n in exact['bids']}
  assert set(values)==IDS and all(0<v<=28 for v in values.values());e['minimums_draft']=exact;save()
  write('bids','/api/advert/v1/bids','PATCH',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=n,bid_kopecks=28,placement='search')for n in sorted(IDS)])]))
  verified('bids',wait(lambda:check(t.campaign(cid),True)))
  before=t.budget(cid);assert before==0;e['before_budget']=before;save()
  write('funding','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=500,type=source))
  def funded():
   b=t.budget(cid);assert b==500;return b
  e['funded_budget']=wait(funded);verified('funding',e['funded_budget'])
  check(t.campaign(cid),True)
  write('start','/adv/v0/start?id='+str(cid),'GET')
  after=wait(lambda:check(t.campaign(cid),True,True));e['after']=after;verified('start',after)
  e.update(status='verified',after_budget=t.budget(cid),verified_at=stamp());save()
  child=ROOT+'campaign:'+str(cid)
  receipt=dict(status='verified',before=e['before'],after=after,before_budget=0,after_budget=e['after_budget'],funding_cny=500,steps=e['steps'],verified_at=e['verified_at'],authorization_key=ROOT+'approval')
  assert db.create(child,receipt)
  registry=db.get('china_agent:verified_campaign_state:v1')or{}
  registry[str(cid)]=child;db.put('china_agent:verified_campaign_state:v1',registry)
  tracking=db.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={})
  tracking.setdefault('plans',{})['owner-bags-search-ten-20261117']=dict(status='active',campaign_ids=[cid],started_at=e['verified_at'],execution_key=child,budget_cny=500,items=[dict(name=a['name'],payment_type='cpc',bid_type='manual',placements=['search'],budget_cny=500,auto_topup=False,skus=[dict(nm_id=n,bid_minor=28)for n in sorted(IDS)])],existing_reports=True)
  db.put('china_agent:new_ad_tests:tracking:v1',tracking)
  e.update(reporting_registered=True,execution_receipt_key=child,first_complete_msk_day='2026-11-18',first_early_review_msk_day='2026-11-19',telegram_calls=0,model_calls=0);save()
 except Exception as ex:
  e.update(status='uncertain' if e.get('status')=='uncertain' or any(s['status']in('submitting','accepted')for s in e['steps'].values()) else 'blocked',reason=str(ex)[:250] or type(ex).__name__);save();raise
 finally:requests.sessions.Session.request=original_http
 print(json.dumps(dict(status=e['status'],campaign_id=e.get('campaign_id'),wb_writes=e['wb_writes'])))
if __name__=='__main__':main()
