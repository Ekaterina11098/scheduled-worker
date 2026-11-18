"""Exact owner-approved gray6 black7 recommendations launch; no Telegram or repeat writes."""
import os,json,time
from datetime import datetime,timezone
import requests
from china_cloud_cost_control import Cache,stamp
from china_new_ads import Transport
from china_moysklad_read import read_stock
from china_morning_readiness import current_prices,published_stock
ROOT='china_agent:owner_fur_recommendations:2026-11-19:v1:'
IDS={2216111729,2216167898}
def check(c,bids=False,active=False):
 assert c['currency']=='CNY' and c['bid_type']=='manual'
 assert c['settings']['name']=='Шубы 6 и 7 — рекомендации — тест19.11' and c['settings']['payment_type']=='cpc'
 assert c['settings']['placements']==dict(search=False,recommendations=True)
 assert len(c['nm_settings'])==2 and {n['nm_id'] for n in c['nm_settings']}==IDS
 assert all(n['subject']['id']==4377 for n in c['nm_settings'])
 if bids:assert all(n['bids_kopecks']['recommendations']==38 and n['bids_kopecks'].get('search',0)==0 for n in c['nm_settings'])
 assert c['status']==(9 if active else 4)
 return c
def main():
 db=Cache();a=db.get(ROOT+'approval')
 assert a['status']=='approved' and a['owner_id']==5122667182 and set(a['nm_ids'])==IDS
 assert a['bid_minor']==38 and a['funding_cny']==100 and a['placement']=='recommendations' and a['no_daily_limits'] is True
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
  old_ids=[41756218,41925305];olds={str(cid):t.campaign(cid) for cid in old_ids};assert all(c['status'] in(7,11) for c in olds.values());e['old_before']=olds;save()
  cfg=t.config();assert cfg['currency']=='CNY' and cfg['minTopUp']<=10000 and 38%cfg['cpcStep']==0 and 38<=cfg['cpcMaxBid']
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
  assert not any(c['id'] not in old_ids and c['status']in(4,9) and IDS & {n['nm_id'] for n in c.get('nm_settings',[])} for c in states),'Unexpected duplicate fur campaign'
  class PriceIO:
   def __init__(self):self.token=os.environ['WB_TOKEN_3']
   def wb(self,path):
    r=requests.get('https://discounts-prices-api.wildberries.ru'+path,headers={'Authorization':self.token},timeout=45);r.raise_for_status();return r.json()['data']
  pio=PriceIO();price_rows=[]
  for nm in sorted(IDS):
   data=pio.wb('/api/v2/list/goods/filter?limit=100&offset=0&filterNmID='+str(nm))
   goods=[x for x in data['listGoods'] if x['nmID']==nm];assert len(goods)==1
   g=goods[0];assert g['discount']==50 and g['currencyIsoCode4217']=='CNY'
   vals={x['discountedPrice'] for x in g['sizes']};assert vals=={404}
   price_rows.append(dict(nm_id=nm,article=g['vendorCode'],seller_price=404,size_ids=[x['sizeID'] for x in g['sizes']]))
  prices=dict(rows=price_rows,observed_at=stamp());stock=read_stock(['6-furcoat-gray','7-furcoat-black'],warehouse_role='msk')
  assert stock['coverage_complete'] and stock['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
  pub=published_stock(pio,prices,sorted(IDS));assert all(v>0 for v in pub['amounts'].values())
  assert set(pub['amounts'])==set(map(str,IDS)) or set(pub['amounts'])==IDS
  rows={r['article']:r for r in stock['rows']};econ_ref=db.get('china_agent:owner_fur_price_test:2026-11-18:v1:tracking')['target_economics'];fx=db.get('china_agent:owner_fur18_ready:v1:plan')['economics']['fx_rub_cny']
  econ={}
  for pr in prices['rows']:
   nm=str(pr['nm_id']);assert int(nm)in IDS and pr['seller_price']==404
   st=rows[pr['article']];assert st['stock']-st['reserve']>0 and st['price']>0
   baseline=econ_ref['rows'][nm];q=baseline['buyout'];assert q==.3 and baseline['buyout_fallback'] is True
   margin=q*(404*.72-st['price']/100/fx)-38;stress=.25*(404*.72-st['price']/100/fx)-38
   assert margin>0 and stress>0,'Current preliminary economy no longer positive'
   econ[nm]=dict(seller_price_cny=404,own_cogs_rub=st['price']/100,stock_free=st['stock']-st['reserve'],buyout=q,buyout_fallback=True,buyout_source='dated18Nov own settled sample absent; approved planned30%',own_sample_observed_source='china_agent:owner_fur_price_test:2026-11-18:v1:tracking',expected_margin_before_ads_cny=margin,stress_margin_before_ads_cny=stress,commission_pct=20,tax_pct=5,payment_reserve_pct=3,logistics_cny=38,fx_rub_per_cny=fx,fx_date='2026-11-18',preliminary=True,unknown_reverse_shared_costs=True,stock_price_checked_at=stamp())
  e.update(preflight_prices=prices,preflight_stock=stock,published_stock=pub,economics=econ);save()
  mins=req('/api/advert/v1/bids/min','POST',dict(advert_id=41925305,nm_ids=sorted(IDS),payment_type='cpc',placement_types=['recommendation']))
  values={n['nm_id']:next(b['value'] for b in n['bids'] if b['type']=='recommendation' and b['currency']=='CNY')for n in mins['bids']}
  assert set(values)==IDS and all(0<v<=38 for v in values.values());e['minimums_before']=mins;save()
  r=write('create','/adv/v2/seacat/save-ad','POST',dict(name=a['name'],nms=sorted(IDS),bid_type='manual',payment_type='cpc',placement_types=['recommendations']))
  cid=r if type(r)is int else r.get('advertId') if isinstance(r,dict)else None
  assert type(cid)is int and cid>0
  e['campaign_id']=cid;save();draft=wait(lambda:check(t.campaign(cid)));e['before']=draft;verified('create',draft)
  write('bids','/api/advert/v1/bids','PATCH',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=n,bid_kopecks=38,placement='recommendations')for n in sorted(IDS)])]))
  verified('bids',wait(lambda:check(t.campaign(cid),True)))
  before=t.budget(cid);assert before==0;e['before_budget']=before;save()
  write('funding','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=100,type=source))
  def funded():
   b=t.budget(cid);assert b==100;return b
  e['funded_budget']=wait(funded);verified('funding',e['funded_budget'])
  check(t.campaign(cid),True);assert all(t.campaign(int(k))==v for k,v in olds.items())
  write('start','/adv/v0/start?id='+str(cid),'GET')
  after=wait(lambda:check(t.campaign(cid),True,True));e['after']=after;verified('start',after)
  old={str(oid):t.campaign(oid) for oid in old_ids};assert old==e['old_before'],'Old campaigns unexpectedly changed'
  e.update(status='verified',old_after=old,after_budget=t.budget(cid),verified_at=stamp());save()
  child=ROOT+'campaign:'+str(cid)
  receipt=dict(status='verified',before=e['before'],after=after,before_budget=0,after_budget=e['after_budget'],funding_cny=100,steps=e['steps'],verified_at=e['verified_at'],authorization_key=ROOT+'approval')
  assert db.create(child,receipt)
  registry=db.get('china_agent:verified_campaign_state:v1')or{}
  registry[str(cid)]=child;db.put('china_agent:verified_campaign_state:v1',registry)
  tracking=db.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={})
  tracking.setdefault('plans',{})['owner-fur-recommendations-20261119']=dict(status='active',campaign_ids=[cid],started_at=e['verified_at'],execution_key=child,budget_cny=100,items=[dict(name=a['name'],payment_type='cpc',bid_type='manual',placements=['recommendations'],budget_cny=100,auto_topup=False,skus=[dict(nm_id=n,bid_minor=38)for n in sorted(IDS)])],existing_reports=True,economics=e['economics'],evaluation=dict(excluded_change_day='2026-11-19',first_full_day='2026-11-20',earliest_review='2026-11-21'))
  db.put('china_agent:new_ad_tests:tracking:v1',tracking)
 except Exception as ex:
  e.update(status='uncertain' if e.get('status')=='uncertain' or any(s['status']in('submitting','accepted')for s in e['steps'].values()) else 'blocked',reason=str(ex)[:250] or type(ex).__name__);save();raise
 print(json.dumps(dict(status=e['status'],campaign_id=e.get('campaign_id'),wb_writes=e['wb_writes'])))
if __name__=='__main__':main()


