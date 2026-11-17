"""Exact approved additions; no funding, Telegram, stock or other changes."""
import os,json,time,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_new_ads import Transport
ROOT='china_agent:owner_add680282:2026-11-17:v1'
CID=41298169
IDS={1473243090,1473245499}

def main():
 c=Cache();w=WB();a=c.get(ROOT+':approval')
 assert a['status']=='approved' and a['owner_id']==5122667182 and set(a['nm_ids'])==IDS and a['campaign_id']==CID and a['bid_minor']==28
 assert a['funding_allowed'] is False and a['telegram_allowed'] is False and a['other_actions_allowed'] is False
 def authority():
  assert c.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(c,w)
 old=c.get(ROOT+':execution')
 if old:
  assert old['status']=='verified','Existing execution: read-only reconciliation required'
  print('Already verified; no writes');return
 e=dict(status='preflight',approval_key=ROOT+':approval',steps={},wb_writes=0,funding_cny=0,telegram_calls=0,stock_writes=0,model_calls=0,created_at=stamp())
 assert c.create(ROOT+':execution',e)
 def save():c.put(ROOT+':execution',e)
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/') and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':
   ok=m=='GET' and u.path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v3/fullstats') or m=='POST' and u.path=='/api/advert/v1/bids/min'
   if m=='PATCH':ok=(u.path=='/adv/v0/auction/nms' and b==e.get('allowed_add')) or (u.path=='/api/advert/v1/bids' and b==e.get('allowed_bid'))
  else:ok=False
  assert ok,'Outside exact additions scope'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 t=Transport(type('AdIO',(),dict(token=w.token))())
 def read():return w.campaigns([CID])[str(CID)]
 def members(cp):return {n['nm_id']:n for n in cp['nm_settings']}
 def base(cp):return {k:cp[k]for k in('id','status','currency','bid_type','settings')}
 def mutate(name,path,body):
  authority();assert name not in e['steps']
  e['steps'][name]=dict(status='submitting',request=body,submitted_at=stamp());save()
  try:r=w.req(path,'PATCH',body,write=True)
  except Exception:e['steps'][name]['status']='uncertain';save();raise
  e['wb_writes']+=1;e['steps'][name].update(status='accepted',response=r);save()
 def poll(fn):
  for i in range(8):
   cp=read()
   if fn(cp):return cp
   if i<7:time.sleep(5)
  e['last_readback']=cp;save();raise RuntimeError('Readback differs; no mutation replay')
 try:
  before=read();e['before']=before;save()
  assert before['status']==9 and before['currency']=='CNY' and before['bid_type']=='manual' and before['settings']['payment_type']=='cpc'
  assert before['settings']['placements']==dict(search=True,recommendations=False)
  bm=members(before)
  assert all(bm[n]['subject']['id']==50 and bm[n]['bids_kopecks']['search']==28 for n in IDS & set(bm)),'Already present with different settings'
  src=c.get('china_agent:advertising_full_growth:2026-11-17:v1:inputs:midday')
  assert src['status']=='complete' and (datetime.now(timezone.utc)-datetime.fromisoformat(src['observed_at'])).total_seconds()<10800
  for n in IDS:
   model=src['economics']['rows'][str(n)]
   assert src['subjects']['by_nm'][str(n)]==50 and model['expected_margin_before_ads_cny']>0 and model['stock_free']>0 and model['published_stock']>0
  e['economics']={str(n):src['economics']['rows'][str(n)]for n in IDS}
  cfg=t.config();assert cfg['currency']=='CNY' and 28%cfg['cpcStep']==0 and 28<=cfg['cpcMaxBid']
  member=next(n for n in before['nm_settings']if n['subject']['id']==50)
  minimum=w.minimums(CID,[member['nm_id']],'search');assert 0<minimum[member['nm_id']]<=28
  e['category_minimum']=minimum
  e['baseline_fullstats']=w.req('/adv/v3/fullstats?ids='+str(CID)+'&beginDate=2026-11-17&endDate=2026-11-17');e['baseline_observed_at']=stamp();save()
  missing=sorted(IDS-set(bm))
  if missing:
   assert base(read())==base(before) and members(read())==bm
   body=dict(nms=[dict(advert_id=CID,nms=dict(add=missing,delete=[]))]);e['allowed_add']=body;save()
   mutate('add','/adv/v0/auction/nms',body)
   added=poll(lambda cp:base(cp)==base(before) and set(members(cp))==set(bm)|IDS and all(members(cp)[n]==v for n,v in bm.items()))
   e['steps']['add'].update(status='verified',after=added,verified_at=stamp());save()
  else:added=before
  am=members(added);assert all(am[n]['subject']['id']==50 for n in IDS)
  needs=sorted(n for n in IDS if am[n]['bids_kopecks'].get('search')!=28)
  if needs:
   body=dict(bids=[dict(advert_id=CID,nm_bids=[dict(nm_id=n,bid_kopecks=28,placement='search')for n in needs])]);e['allowed_bid']=body;save()
   assert members(read())==am
   mutate('bids','/api/advert/v1/bids',body)
  def final(cp):
   m=members(cp)
   return base(cp)==base(before) and set(m)==set(bm)|IDS and all(m[n]==v for n,v in bm.items()) and all(m[n]['subject']['id']==50 and m[n]['bids_kopecks'].get('search')==28 and m[n]['bids_kopecks'].get('recommendations',0)==0 for n in IDS)
  after=poll(final)
  if needs:e['steps']['bids'].update(status='verified',verified_at=stamp())
  at=stamp();items=[dict(id=str(CID)+':add:'+str(n),kind='ad_add_sku',campaign_id=CID,nm_id=n,placement='search',target_minor=28,status='verified',already_present=n in bm,verified_at=at)for n in sorted(IDS)]
  e.update(status='verified',after=after,items=items,verified_at=at,first_complete_msk_day='2026-11-18',first_early_review_msk_day='2026-11-19');save()
  registry=c.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=ROOT+':execution';c.put('china_agent:verified_campaign_state:v1',registry)
  alias='china_agent:ad_rule_execution:owner-add680282-17:v1';c.put(alias,dict(status='done',canonical_source_execution_key=ROOT+':execution',items=[dict(i,before=before,after=after,source_execution_key=ROOT+':execution')for i in items],wb_writes=0,alias_of_verified_batch=True))
  tracking=c.get('china_agent:bid_raise_tracking:v1')or dict(items={})
  for i in items:
   tracking.setdefault('items',{})[str(CID)+':'+str(i['nm_id'])]=dict(status='active',plan=i,started_at=at,verified_at=at,execution_key=ROOT+':execution',target_drr_pct=5,first_complete_msk_day='2026-11-18',first_early_review_msk_day='2026-11-19',auto_revert_authorized=False)
  c.put('china_agent:bid_raise_tracking:v1',tracking)
  assert c.get('china_agent:verified_campaign_state:v1')[str(CID)]==ROOT+':execution' and c.get(alias)['status']=='done'
  e['reporting_registered']=True;save()
  print(json.dumps(dict(status=e['status'],campaign_id=CID,nm_ids=sorted(IDS),bid_cny=.28,wb_writes=e['wb_writes'],funding_cny=0,telegram_calls=0)))
 except Exception as ex:
  e.update(status='uncertain'if e['steps']else'blocked',reason=type(ex).__name__+': '+str(ex)[:180]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

