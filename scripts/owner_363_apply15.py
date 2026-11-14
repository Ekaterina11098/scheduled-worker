"""Explicit owner transfer10 + deposit100. Telegram prohibited by latest owner correction."""
import copy,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_363_transfer_apply:2026-11-15:v1'
SRC=41296363;DST=41270309
IDS=[1473242579,1473242767,1473244987,1473245001,1473242761,1473246045,1473243935,1473246054,1473246042,1473246043]
def keyed(c):return {n['nm_id']:n for n in c['nm_settings']}
def main():
 io=AdvertisingIO();auth=io.get(ROOT+':authorization')
 scope=dict(source_campaign=SRC,target_campaign=DST,nm_ids=sorted(IDS),placement='recommendations',bid_minor=28,amount_cny=100,source_resume=False,telegram_send=False)
 assert auth and auth['status']=='approved'and auth['owner_id']==5122667182 and auth['scope']==scope
 assert datetime.now(timezone.utc)<datetime.fromisoformat(auth['expires_at'])
 if io.get(ROOT+':execution'):print('Existing journal retained, no automatic replay');return
 proposal=io.get('china_agent:owner_363_transfer:2026-11-15:v1:proposal')
 assert proposal['status']=='proposal_only'and sorted(r['nm_id']for r in proposal['rows'])==sorted(IDS)
 root=dict(status='preflight',authorization_key=ROOT+':authorization',wb_writes=0,steps=[],telegram_calls=0,telegram_delivery_suppressed_by_owner=True,model_calls=0)
 assert io.create(ROOT+':execution',root)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(root)))
 old=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json')
  if u.hostname=='api.telegram.org'or 'openai'in(u.hostname or''):raise ValueError('Latest owner forbids Telegram; model calls forbidden')
  if u.hostname=='advert-api.wildberries.ru':
   allowed=(m=='GET'and u.path in ['/adv/v1/promotion/count','/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance'])or(m=='POST'and u.path in ['/api/advert/v2/budget','/api/advert/v1/bids/min'])
   if u.path=='/adv/v0/auction/nms':
    allowed=m=='PATCH'and b in [dict(nms=[dict(advert_id=DST,nms=dict(add=sorted(root.get('missing_ids',[])),delete=[]))]),dict(nms=[dict(advert_id=SRC,nms=dict(add=[],delete=sorted(root.get('remove_ids',[]))))])]
   if u.path=='/api/advert/v1/bids':
    allowed=m=='PATCH'and b==root.get('allowed_bid_body')
   if u.path=='/adv/v1/budget/deposit':
    allowed=m=='POST'and parse_qs(u.query)=={'id':[str(DST)]}and b==dict(sum=100,type=root.get('wallet_type'))
   if not allowed:raise ValueError('WB action outside exact owner scope')
  elif (u.hostname or'').endswith('wildberries.ru'):
   assert m=='GET'or m=='POST'and u.path=='/api/v3/stocks/2126188','No price/stock mutations'
  elif (u.hostname or'').endswith('moysklad.ru'):assert m=='GET'
  elif not url.startswith(io.url+'/rest/v1/'):raise ValueError('Unrelated network request')
  return old(session,method,url,**kw)
 requests.sessions.Session.request=guard
 from china_cloud_cost_control import Cache,WB,validate_identity
 def req(path,method='GET',body=None):
  time.sleep(1.5);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50)
  if not r.ok:raise RuntimeError('WB HTTP '+str(r.status_code))
  return r.json()if r.content else{}
 def campaigns(ids):
  rows=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts'];assert {c['id']for c in rows}==set(ids)
  return {c['id']:c for c in rows}
 def campaign(cid):return campaigns([cid])[cid]
 def budget():
  r=req('/api/advert/v2/budget','POST',dict(advertIds=[DST]))['adverts'];assert len(r)==1 and r[0]['currency']=='CNY';return r[0]['total']
 def mutate(kind,path,method,body,verify):
  step=dict(kind=kind,status='submitting',request=dict(path=path,method=method,body=body),submitted_at=datetime.now(timezone.utc).isoformat())
  root['steps'].append(step);save()
  try:
   step['response']=req(path,method,body);step['status']='accepted';root['wb_writes']+=1;save()
   for _ in range(12):
    after=verify()
    if after is not None:
     step.update(status='verified',after=after,verified_at=datetime.now(timezone.utc).isoformat());save();return after
    time.sleep(5)
   raise ValueError('WB readback not verified; never replay mutation')
  except Exception as e:step.update(status='uncertain',reason=type(e).__name__);root['status']='uncertain';save();raise
 try:
  validate_identity(Cache(),WB())
  inv=req('/adv/v1/promotion/count');active=sorted({r['advertId']for g in inv['adverts']if g['status']==9 for r in g['advert_list']})
  current=campaigns(sorted(set(active)|{SRC,DST}));src=current[SRC];dst=current[DST]
  assert src['status']==11 and dst['status']==9
  for c in [src,dst]:assert c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'and c['settings']['placements']==dict(search=False,recommendations=True)and c['restrictions']['can_change_nms']
  assert {n['subject']['id']for c in[src,dst]for n in c['nm_settings']}=={50}
  for nm in IDS:
   assert all(cid==DST or nm not in keyed(c)for cid,c in current.items()if c['status']==9),'Duplicate active SKU'
   if nm in keyed(dst):assert keyed(dst)[nm]['bids_kopecks']==dict(search=0,recommendations=28)
   else:assert nm in keyed(src),'Missing from both campaign memberships'
  root.update(before_source=src,before_target=dst,missing_ids=sorted(set(IDS)-set(keyed(dst))));save()
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['cpcStep']==1 and cfg['minTopUp']<=10000
  quote=req('/api/advert/v1/bids/min','POST',dict(advert_id=SRC,nm_ids=sorted(IDS),payment_type='cpc',placement_types=['recommendation']))
  assert {r['nm_id']for r in quote['bids']}==set(IDS)
  assert all([b['value']for b in r['bids']if b['type']=='recommendation'and b['currency']=='CNY']==[28]for r in quote['bids'])
  from china_morning_readiness import current_prices,published_stock
  from china_moysklad_read import read_stock
  prices=current_prices(io,IDS);pub=published_stock(io,prices,IDS);stock=read_stock([p['article']for p in prices['rows']]);stocks={r['article'].casefold():r for r in stock['rows']}
  assert stock['coverage_complete']and not pub['missing_nm_ids']
  for p in prices['rows']:
   previous=next(r for r in proposal['rows']if r['nm_id']==p['nm_id']);s=stocks[p['article'].casefold()]
   assert p['article']==previous['article']and p['seller_price']==previous['price_cny']and s['price']>0 and s['stock']-s['reserve']>0 and pub['amounts'][str(p['nm_id'])]>0
   delta=max(0,s['price']/100-previous['cogs_rub'])/12.3149*previous['buyout']
   assert min(previous['expected_margin_before_ads_cny'],previous['stress_margin_before_ads_cny'])>delta
  root['preflight']=dict(prices=prices,published_stock=pub,stock=stock,minimums=quote,config=cfg);save()
  wallet=req('/adv/v1/balance');assert wallet['currency']=='CNY'
  root['wallet_type']=0 if wallet.get('balance',0)>=100 else 1 if wallet.get('net',0)>=100 else None
  assert root['wallet_type']is not None,'Insufficient available CNY wallet'
  # Checkpoints are durable before each mutation. An existing execution never replays.
  if root['missing_ids']:
   def added():
    c=campaign(DST);old=keyed(dst);new=keyed(c)
    return c if c['status']==9 and c['settings']==dst['settings']and set(new)==set(old)|set(IDS)and all(new[nm]==n for nm,n in old.items())and all(new[nm]['subject']['id']==50 for nm in IDS)else None
   dst=mutate('ad_add_skus','/adv/v0/auction/nms','PATCH',dict(nms=[dict(advert_id=DST,nms=dict(add=root['missing_ids'],delete=[]))]),added)
  need=[nm for nm in IDS if keyed(dst)[nm]['bids_kopecks']!=dict(search=0,recommendations=28)]
  if need:
   assert all(keyed(dst)[nm]['bids_kopecks'].get('search',0)==0 for nm in need)
   root['allowed_bid_body']=dict(bids=[dict(advert_id=DST,nm_bids=[dict(nm_id=nm,placement='recommendations',bid_kopecks=28)for nm in sorted(need)])]);save()
   before_bid=copy.deepcopy(dst)
   def bids():
    c=campaign(DST);return c if c['status']==9 and c['settings']==dst['settings']and set(keyed(c))==set(keyed(dst))and all(keyed(c)[nm]['bids_kopecks']==dict(search=0,recommendations=28)for nm in IDS)and all(keyed(c)[nm]==n for nm,n in keyed(before_bid).items()if nm not in need)else None
   dst=mutate('ad_set_bids','/api/advert/v1/bids','PATCH',root['allowed_bid_body'],bids)
  assert all(keyed(dst)[nm]['bids_kopecks']==dict(search=0,recommendations=28)for nm in IDS)
  root['verified_target_before_removal']=dst;root['before_budget']=budget();save()
  def funded():
   value=budget();return dict(total=value,currency='CNY')if root['before_budget']+98<=value<=root['before_budget']+100 else None
  cash=mutate('topup_campaign','/adv/v1/budget/deposit?id='+str(DST),'POST',dict(sum=100,type=root['wallet_type']),funded)
  root['after_budget']=cash['total'];save()
  # Re-read target first: no source deletion before all10 exact target bids are verified.
  dst=campaign(DST);assert dst['status']==9 and all(keyed(dst)[nm]['bids_kopecks']==dict(search=0,recommendations=28)for nm in IDS)
  source_now=campaign(SRC);assert source_now['status']==11 and keyed(source_now)==keyed(src)
  root['remove_ids']=sorted(set(IDS)&set(keyed(source_now)));save()
  if root['remove_ids']:
   def removed():
    c=campaign(SRC);return c if c['status']==11 and c['settings']==src['settings']and keyed(c)=={nm:n for nm,n in keyed(src).items()if nm not in IDS}else None
   src=mutate('ad_exclude_skus','/adv/v0/auction/nms','PATCH',dict(nms=[dict(advert_id=SRC,nms=dict(add=[],delete=root['remove_ids']))]),removed)
  final=campaigns([SRC,DST]);assert final[SRC]['status']==11 and not(set(IDS)&set(keyed(final[SRC])))and final[DST]['status']==9 and all(keyed(final[DST])[nm]['bids_kopecks']==dict(search=0,recommendations=28)for nm in IDS)
  root.update(status='verified',after_source=final[SRC],after_target=final[DST],verified_at=datetime.now(timezone.utc).isoformat());save()
  reg=io.get('china_agent:verified_campaign_state:v1')or{}
  for cid,before,after in[(SRC,root['before_source'],final[SRC]),(DST,root['before_target'],final[DST])]:
   key=ROOT+':campaign:'+str(cid);value=dict(status='verified',before=before,after=after,verified_at=root['verified_at'],parent=ROOT+':execution')
   assert io.create(key,value);reg[str(cid)]=key
  io.put('china_agent:verified_campaign_state:v1',reg)
  print(json.dumps(dict(status='verified',transferred=len(IDS),source_status=final[SRC]['status'],target_status=final[DST]['status'],after_budget=root['after_budget'],writes=root['wb_writes'],telegram_calls=0)))
 except Exception as e:
  if root['status']!='uncertain':root.update(status='blocked'if not root['wb_writes']else'attention_required',error=type(e).__name__+': '+str(e));save()
  raise
if __name__=='__main__':main()
