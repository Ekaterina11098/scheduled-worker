"""Execute exact approved small-sample test additions; no Telegram/funding."""
import copy,json,time,requests,math
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_fur6_return:2026-11-21:v1'
GROUPS=[dict(cid=42022679,zone='recommendations',subject=4377,bid=38,items={2216111729:'6'})]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO()
 previous=io.get(ROOT+':execution')
 if previous:
  assert previous['status']=='verified','Existing execution: no blind retry'
  print('Already verified');return
 a=dict(status='approved',owner_id=5122667182,groups=GROUPS,telegram_send=False,funding=False,recorded_at=now(),instruction='Owner explicitly says return gray6 to campaign after reviewing negative preliminary economics. Restore only6 to42022679 at prior0.38; noTG/funding/otherchanges.')
 if not io.get(ROOT+':approval'):assert io.create(ROOT+':approval',a)
 e=dict(status='preflight',created_at=now(),groups=[],wb_writes=0,telegram_calls=0,model_calls=0,approval_key=ROOT+':approval');assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);host=u.hostname or'';path=u.path;m=method.upper();body=kw.get('json')or{}
  if host=='api.telegram.org'or'openai'in host:raise ValueError('No Telegram/model')
  if host.endswith('moysklad.ru'):assert m=='GET'
  if host.endswith('wildberries.ru'):
   allowed=m=='GET'and path in('/api/advert/v2/adverts','/adv/v1/promotion/count','/api/advert/v1/config','/api/v2/list/goods/filter')or m=='POST'and path in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2126188')
   if m=='PATCH'and path=='/adv/v0/auction/nms':allowed=any(body==s.get('add_body')for s in e['groups'])
   if m=='PATCH'and path=='/api/advert/v1/bids':allowed=any(body==s.get('bid_body')for s in e['groups'])
   assert allowed,'Outside exact owner-approved gray6 return'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.2);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50);r.raise_for_status();return r.json()if r.content else{}
 def camp(cid):
  c=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(c)==1 and c[0]['id']==cid;return c[0]
 def norm(c):
  d={k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
 def verify(c,before,added,bid,zone):
  assert all(c[k]==before[k]for k in('id','status','currency','settings','bid_type'))
  old={n['nm_id']:n for n in before['nm_settings']};new={n['nm_id']:n for n in c['nm_settings']}
  assert set(new)==set(old)|set(added)and all(new[n]==v for n,v in old.items()),'Whole-package membership/bid mismatch'
  if bid is not None:assert all(new[n]['bids_kopecks'].get(zone)==bid and new[n]['bids_kopecks'].get('search'if zone=='recommendations'else'recommendations',0)==0 for n in added)
  return c
 def write(s,name,path,body):
  assert name not in s['steps']
  s['steps'][name]=dict(status='submitting',path=path,body=body,submitted_at=now());save()
  try:r=req(path,'PATCH',body)
  except Exception:s['steps'][name]['status']='uncertain';e['status']='uncertain';save();raise
  s['steps'][name].update(status='accepted',response=r);e['wb_writes']+=1;save()
 try:
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
  listing=req('/adv/v1/promotion/count');ids=sorted({x['advertId']for g in listing.get('adverts',[])for x in g.get('advert_list',[])})
  states=[]
  for start in range(0,len(ids),50):states+=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids[start:start+50])))['adverts']
  byid={c['id']:c for c in states};allids={n for g in GROUPS for n in g['items']};assert len(allids)==1
  prices=current_prices(io,sorted(allids));assert {p['nm_id']for p in prices['rows']}==allids
  expected={n:art for g in GROUPS for n,art in g['items'].items()};assert all(p['article'].split('-')[0]==expected[p['nm_id']]for p in prices['rows'])
  stock=read_stock([p['article']for p in prices['rows']],warehouse_role='msk');assert stock['coverage_complete']
  pub=published_stock(io,prices,sorted(allids));assert not pub['missing_nm_ids']
  v=io.get('china_agent:advertising_full_growth:2026-11-21:v1:inputs');assert v['status']=='complete'
  assert (datetime.now(timezone.utc)-datetime.fromisoformat(v['own']['observed_at'])).total_seconds()<48*3600
  models=model_rows(dict(products=v['own'],prices=prices,stock=stock,fx=v['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
  assert not models['missing']and set(models['rows'])==set(map(str,allids))
  for n,m in models['rows'].items():
   m.update(published_stock=pub['amounts'][n],published_stock_observed_at=pub['observed_at'])
   assert m['stock_free']>0 and m['published_stock']>0 and m.get('sample_size',0)<20
   assert all(math.isfinite(m[k])for k in('expected_margin_before_ads_cny','own_cogs_rub','seller_price_cny','buyout'))
  e['preflight']=dict(prices=prices,stock=stock,published=pub,economics=models);save()
  for g in GROUPS:
   before=byid[g['cid']];assert before['status']==9 and before['currency']=='CNY'and before['bid_type']=='manual'and before['settings']['payment_type']=='cpc'
   assert before['settings']['placements'].get(g['zone'])is True and not before['settings']['placements'].get('search'if g['zone']=='recommendations'else'recommendations')
   old={n['nm_id']for n in before['nm_settings']};wanted=set(g['items'])-old
   duplicate=[(c['id'],n['nm_id'])for c in states if c['id']!=g['cid']and c['status']in(9,11)and c['settings']['placements'].get(g['zone'])for n in c['nm_settings']if n['nm_id']in wanted]
   assert not duplicate,'Same-placement duplicate: '+str(duplicate)
   representative=next(n['nm_id']for n in before['nm_settings']if n['subject']['id']==g['subject']);typ='search'if g['zone']=='search'else'recommendation'
   quote=req('/api/advert/v1/bids/min','POST',dict(advert_id=g['cid'],nm_ids=[representative],payment_type='cpc',placement_types=[typ]))
   minimum=[b['value']for row in quote['bids']for b in row['bids']if b['type']==typ and b['currency']=='CNY'];assert minimum==[g['bid']]and g['bid']%cfg['cpcStep']==0
   s=dict(cid=g['cid'],before=before,added_nm_ids=sorted(wanted),already_present=sorted(set(g['items'])&old),minimum=quote,status='ready',steps={},add_body=dict(nms=[dict(advert_id=g['cid'],nms=dict(add=sorted(wanted),delete=[]))]))
   e['groups'].append(s);save()
  e['status']='running';save()
  for g,s in zip(GROUPS,e['groups']):
   cid=g['cid'];wanted=set(s['added_nm_ids']);before=s['before'];assert norm(camp(cid))==norm(before),'Campaign changed after preflight'
   if wanted:
    write(s,'add','/adv/v0/auction/nms',s['add_body'])
    for attempt in range(12):
     try:added=verify(camp(cid),before,wanted,None,g['zone']);break
     except AssertionError:
      if attempt==11:raise
      time.sleep(3)
    s['steps']['add'].update(status='verified',after=added,verified_at=now());save()
    typ='search'if g['zone']=='search'else'recommendation'
    exact=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=sorted(wanted),payment_type='cpc',placement_types=[typ]))
    minima={row['nm_id']:next(b['value']for b in row['bids']if b['type']==typ and b['currency']=='CNY')for row in exact['bids']}
    assert set(minima)==wanted and all(x==g['bid']for x in minima.values());s['exact_minima']=exact;save()
    changes=[dict(nm_id=n,bid_kopecks=g['bid'],placement=g['zone'])for n in sorted(wanted)if next(x for x in added['nm_settings']if x['nm_id']==n)['bids_kopecks'].get(g['zone'])!=g['bid']]
    if changes:
     s['bid_body']=dict(bids=[dict(advert_id=cid,nm_bids=changes)]);save();write(s,'bid','/api/advert/v1/bids',s['bid_body'])
   for attempt in range(12):
    try:after=verify(camp(cid),before,wanted,g['bid'],g['zone']);break
    except AssertionError:
     if attempt==11:raise
     time.sleep(3)
   time.sleep(3);again=verify(camp(cid),before,wanted,g['bid'],g['zone'])
   if 'bid'in s['steps']:s['steps']['bid'].update(status='verified',after=again,verified_at=now())
   s.update(status='verified',after=again,readbacks=[after,again],verified_at=now());save()
   child=ROOT+':campaign:'+str(cid);assert io.create(child,copy.deepcopy(s))
   registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=child;io.put('china_agent:verified_campaign_state:v1',registry)
  # Final whole package, after all additions. Never assume isolated readbacks remain current.
  finals=[]
  for g,s in zip(GROUPS,e['groups']):finals.append(verify(camp(g['cid']),s['before'],s['added_nm_ids'],g['bid'],g['zone']))
  e.update(status='verified',package_readback=finals,verified_at=now(),added_count=sum(len(s['added_nm_ids'])for s in e['groups']));save()
  tracking=io.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={});day=datetime.now(ZoneInfo('Europe/Moscow')).date()
  for g,s in zip(GROUPS,e['groups']):
   tracking.setdefault('plans',{})['owner-fur6-return-20261121-'+str(g['cid'])]=dict(status='active',campaign_ids=[g['cid']],started_at=s['verified_at'],execution_key=ROOT+':campaign:'+str(g['cid']),owner_approved_small_sample_risk=True,existing_reports=True,auto_topup=False,nm_ids=s['added_nm_ids'],bid_minor=g['bid'],placement=g['zone'],evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))))
  io.put('china_agent:new_ad_tests:tracking:v1',tracking);e['reports_registered']=True;save()
 except Exception as ex:
  if e['status']!='verified':e.update(status='uncertain'if any(x['status']in('submitting','accepted','uncertain')for s in e['groups']for x in s['steps'].values())else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save()
  raise
 print(json.dumps(dict(status=e['status'],added=e['added_count'],wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()
