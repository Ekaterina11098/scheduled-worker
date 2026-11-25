"""Exact owner-approved recovery; no prices, Telegram, daily limits or replay."""
import copy,json,time,hashlib,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
ROOT='china_agent:owner_sales_revival:2026-11-25:v1'
OLD='china_agent:daily_ad_execution:v2:daily-2026-11-25-owner-cash-r1-budgets-0-buttons-d974c438dffcba3063f64dd4-5122667182'
def now():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','bid_type','settings','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda x:x['nm_id']);return d
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');p=io.get(ROOT+':plan-v2')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['plan_sha256']==digest(p)
 assert a['funding']=={'40933588':150,'40945478':100,'41298169':100,'41967612':1850}and a['no_extra_funding']==[]
 assert len(p['raises'])==17 and len(p['additions'])==26 and not p['price_changes']
 def authority():
  assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(Cache(),WB())
 e=io.get(ROOT+':execution')
 if e:
  if e['status']=='verified':print('Already verified, no writes');return
  assert e['status']=='blocked'and e['wb_writes']==0 and not e['ops'],'Existing nonempty operation retained'
  assert io.create(ROOT+':execution-pre-moy429',e),'Existing recovery checkpoint; inspect'
  e=None
 e=dict(status='preflight',created_at=now(),approval_key=ROOT+':approval',plan_sha256=digest(p),ops={},campaigns={},funding={},errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if io.get(ROOT+':execution'):io.put(ROOT+':execution',e)
 else:assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 allowed=None;original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or'';path=u.path+('?' +u.query if u.query else'');b=kw.get('json')
  if host==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif host=='api.moysklad.ru':ok=m=='GET'and u.path.startswith('/api/remap/1.2/')
  elif host=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  elif host=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  elif host=='advert-api.wildberries.ru':
   ok=m=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance')or m=='POST'and u.path in('/api/advert/v1/bids/min','/api/advert/v2/budget')
   if(m,path,b)==allowed:ok=True
  else:ok=False
  assert ok,'Outside exact owner scope '+m+' '+str(host)+u.path
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=55)
  if not r.ok:raise ValueError('WB HTTP '+str(r.status_code)+' '+path.split('?')[0])
  return r.json()if r.content else{}
 def camp(cid):
  rows=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(rows)==1 and rows[0]['id']==cid and rows[0]['currency']=='CNY';return rows[0]
 def budget(cid):
  rows=req('/api/advert/v2/budget','POST',dict(advertIds=[cid]))['adverts'];assert len(rows)==1 and rows[0]['advertId']==cid and rows[0]['currency']=='CNY';return rows[0]['total']
 def write(key,path,body):
  nonlocal allowed
  authority();assert key not in e['ops'],'No uncertain operation replay'
  method='POST'if path.startswith('/adv/v1/budget/deposit')else'PATCH'
  e['ops'][key]=dict(status='submitting',path=path,method=method,body=body,submitted_at=now());save();allowed=(method,path,body)
  try:result=req(path,method,body)
  except Exception:e['ops'][key]['status']='uncertain';save();raise
  finally:allowed=None
  e['ops'][key].update(status='accepted',response=result);e['wb_writes']+=1;save()
 def verify(cid,expected):
  for _ in range(8):
   after=camp(cid)
   if norm(after)==norm(expected):
    again=camp(cid)
    if norm(again)==norm(expected):return again
   time.sleep(3)
  raise ValueError('Whole campaign readback mismatch '+str(cid))
 def register(cid,before,after,items):
  key=ROOT+':campaign:'+str(cid);rec=dict(status='verified',before=before,after=after,items=items,verified_at=now(),authorization_key=ROOT+':approval')
  io.put(key,rec)if io.get(key)else io.create(key,rec)
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=key;io.put('china_agent:verified_campaign_state:v1',registry)
  return key
 try:
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['cpcStep']==1
  quotes=io.get(ROOT+':quotes-v3');assert quotes['status']=='complete'and(datetime.now(timezone.utc)-datetime.fromisoformat(quotes['completed_at'])).total_seconds()<7200
  nms={x['nm_id']for x in p['raises']}|{x['nm']for x in p['additions']}
  prices=current_prices(io,sorted(nms));byprice={r['nm_id']:r for r in prices['rows']}
  frozen=a['economics'];assert set(frozen)=={str(n)for n in nms}
  for nm,g in byprice.items():
   f=frozen[str(nm)];assert g['article']==f['article']and abs(g['seller_price']-f['price'])<0.001 and f['margin']-.08*f['price']>0,'Price/economics changed '+str(nm)
  arts=[r['article']for r in prices['rows']];saved=io.get('china_agent:advertising_full_growth:2026-11-25:v1:inputs');stock=saved['stock'];assert saved['status']=='complete'and (datetime.now(timezone.utc)-datetime.fromisoformat(stock['observed_at'])).total_seconds()<4*3600
  parts=[dict(stock,rows=[r for r in stock['rows']if r['article'].casefold()in{a.casefold()for a in arts}],source_cache='china_agent:advertising_full_growth:2026-11-25:v1:inputs')]
  assert all(z['coverage_complete']and z['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'for z in parts)
  stocks=sum([z['rows']for z in parts],[])
  for art in arts:
   found=[r for r in stocks if r['article'].casefold()==art.casefold()];assert len(found)==1 and found[0]['stock']-found[0]['reserve']>0,'MSK unavailable '+art
  pub=published_stock(io,prices,sorted(nms));assert not pub['missing_nm_ids']and all(pub['amounts'][str(n)]>0 for n in nms)
  e['preflight']=dict(config=cfg,prices=prices,stock=parts,published=pub,observed_at=now());save()
  ids=sorted({x['campaign_id']for x in p['raises']}|{41967612,42088552,42022679})
  cs={cid:camp(cid)for cid in ids};e['protected_before']={str(cid):cs[cid]for cid in(42088552,42022679)};save()
  for cid in ids:
   if cid in(42088552,42022679):continue
   c=cs[cid];assert c['status']==9 and c['settings']['payment_type']=='cpc'and c['bid_type']=='manual'
  for x in p['raises']:
   c=cs[x['campaign_id']];n=next(n for n in c['nm_settings']if n['nm_id']==x['nm_id']);assert n['bids_kopecks'][x['placement']]in(x['old_minor'],x['target_minor'])
   assert c['settings']['placements'][x['placement']]and quotes['quotes'][str(x['campaign_id'])+':'+x['placement']]['values'][str(x['nm_id'])]<=x['target_minor']<=cfg['cpcMaxBid']
  target=cs[41967612];old={n['nm_id']:n for n in target['nm_settings']};assert target['settings']['placements']==dict(search=True,recommendations=False)and target['restrictions']['can_change_nms']
  wanted={x['nm']for x in p['additions']};missing=wanted-set(old);assert len(set(old)|wanted)<=50
  reference=next(n['nm_id']for n in target['nm_settings']if n['subject']['id']==50)
  mini=req('/api/advert/v1/bids/min','POST',dict(advert_id=41967612,nm_ids=[reference],payment_type='cpc',placement_types=['search']))
  assert all(b['value']<=28 for n in mini['bids']for b in n['bids']if b['type']=='search'and b['currency']=='CNY')
  e['status']='running';save()
  # Exact batched raises, preserving every other member and setting.
  for cid in sorted({x['campaign_id']for x in p['raises']}):
   items=[x for x in p['raises']if x['campaign_id']==cid];before=camp(cid);assert norm(before)==norm(cs[cid]);expected=copy.deepcopy(before);bids=[]
   for x in items:
    n=next(n for n in expected['nm_settings']if n['nm_id']==x['nm_id'])
    if n['bids_kopecks'][x['placement']]!=x['target_minor']:bids.append(dict(nm_id=x['nm_id'],bid_kopecks=x['target_minor'],placement=x['placement']));n['bids_kopecks'][x['placement']]=x['target_minor']
   if bids:write(str(cid)+':bids','/api/advert/v1/bids',dict(bids=[dict(advert_id=cid,nm_bids=bids)]))
   after=verify(cid,expected);rec=register(cid,before,after,[dict(x,status='verified')for x in items]);e['campaigns'][str(cid)]=dict(status='verified',receipt=rec,after=after)
   if bids:e['ops'][str(cid)+':bids']['status']='verified'
   save()
  before=camp(41967612);assert norm(before)==norm(target)
  if missing:write('41967612:members','/adv/v0/auction/nms',dict(nms=[dict(advert_id=41967612,nms=dict(add=sorted(missing),delete=[]))]))
  for _ in range(8):
   actual=camp(41967612);members={n['nm_id']:n for n in actual['nm_settings']}
   if set(members)==set(old)|wanted and all(members[n]==v for n,v in old.items()):break
   time.sleep(3)
  else:raise ValueError('Addition membership mismatch')
  assert actual['settings']==before['settings']and actual['status']==9
  q=req('/api/advert/v1/bids/min','POST',dict(advert_id=41967612,nm_ids=sorted(wanted),payment_type='cpc',placement_types=['search']))
  vals={n['nm_id']:next(b['value']for b in n['bids']if b['currency']=='CNY'and b['type']=='search')for n in q['bids']};assert set(vals)==wanted and all(v<=28 for v in vals.values())
  expected=copy.deepcopy(actual);bids=[]
  for n in expected['nm_settings']:
   if n['nm_id']in wanted:
    assert n['subject']['id']==50 and n['bids_kopecks']['recommendations']==0
    if n['bids_kopecks']['search']!=28:bids.append(dict(nm_id=n['nm_id'],bid_kopecks=28,placement='search'));n['bids_kopecks']['search']=28
  if bids:write('41967612:bids','/api/advert/v1/bids',dict(bids=[dict(advert_id=41967612,nm_bids=bids)]))
  after=verify(41967612,expected);rec=register(41967612,before,after,[dict(x,status='verified')for x in p['additions']]);e['campaigns']['41967612']=dict(status='verified',receipt=rec,after=after,new_count=len(missing))
  for k in('41967612:members','41967612:bids'):
   if k in e['ops']:e['ops'][k]['status']='verified'
  save()
  # Credit all seven already verified morning deposits; never repeat them.
  prior=io.get(OLD);assert prior['status']=='done'and len(prior['items'])==7 and all(x['status']=='verified'for x in prior['items'])
  credited={str(x['before']['id']):x['request']['body']['sum']for x in prior['items']};assert credited=={'40933588':3150,'41155909':200,'41270309':350,'41298169':350,'41325622':100,'41332083':250,'42088552':400}
  e['credited_prior_funding']=dict(execution_key=OLD,amounts=credited,total_cny=4800);save()
  wallet=req('/adv/v1/balance');assert wallet['currency']=='CNY';source=0 if wallet.get('balance',0)>=2200 else 1 if wallet.get('net',0)>=2200 else None;assert source is not None,'Wallet insufficient'
  for cidstr,amount in a['funding'].items():
   cid=int(cidstr);assert amount*100>=cfg['minTopUp'];before=camp(cid);initial=budget(cid);assert norm(before)==norm(e['campaigns'][cidstr]['after'])
   state=dict(status='ready',amount_cny=amount,before_budget=initial,before=before);e['funding'][cidstr]=state;save()
   write(cidstr+':deposit','/adv/v1/budget/deposit?id='+cidstr,dict(sum=amount,type=source))
   for _ in range(8):
    after_balance=budget(cid)
    if after_balance>=initial+amount-3:break
    time.sleep(3)
   else:raise ValueError('Deposit readback not resolved '+cidstr)
   assert norm(camp(cid))==norm(before);state.update(status='verified',after_budget=after_balance,verified_at=now());e['ops'][cidstr+':deposit']['status']='verified';save()
  final={cid:camp(cid)for cid in ids}
  assert all(norm(final[cid])==norm(e['campaigns'][str(cid)]['after'])for cid in ids if cid not in(42088552,42022679))
  assert all(norm(final[cid])==norm(cs[cid])for cid in(42088552,42022679))
  freshprices=current_prices(io,sorted(nms));assert sorted(prices['rows'],key=lambda x:x['nm_id'])==sorted(freshprices['rows'],key=lambda x:x['nm_id'])
  tracking=io.get('china_agent:bid_raise_tracking:v1')or{'items':{}}
  for x in p['raises']:
   tracking.setdefault('items',{})[str(x['campaign_id'])+':'+str(x['nm_id'])]=dict(status='active',plan=x,started_at=e['created_at'],verified_at=now(),execution_key=ROOT+':campaign:'+str(x['campaign_id']),target_drr_pct=8,first_complete_msk_day='2026-11-26',first_early_review_msk_day='2026-11-27',auto_revert_authorized=False)
  io.put('china_agent:bid_raise_tracking:v1',tracking)
  io.create(ROOT+':tracking',dict(status='active',raises=p['raises'],additions=p['additions'],funding=a['funding'],target_drr_pct=8,first_complete_msk_day='2026-11-26',first_early_review_msk_day='2026-11-27',execution_key=ROOT+':execution',auto_changes=False,auto_funding=False))
  e.update(status='verified',completed_at=now(),final_campaigns={str(k):v for k,v in final.items()},additional_funded_cny=2200,prices_unchanged_verified=True,protected_unchanged_verified=True,reporting_registered=True);save()
 except Exception as ex:
  e.update(status='uncertain'if any(x['status']in('submitting','accepted','uncertain')for x in e['ops'].values())else'partial'if e['wb_writes']else'blocked',reason=type(ex).__name__+': '+str(ex)[:250]);save();raise
 finally:requests.sessions.Session.request=original
 print(json.dumps(dict(status=e['status'],raises=17,additions=26,funded=2200,wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()