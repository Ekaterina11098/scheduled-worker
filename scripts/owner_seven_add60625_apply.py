"""One exact owner-confirmed recommendation addition, no funding/prices/TG."""
import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import Reader
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_seven_recovery25_apply:add606:v1'
CID=40933588
NM=1473246040
ART='606-MadisonBag-beige'
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','bid_type','settings','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['campaign_id']==CID and a['nm_id']==NM and a['bid_minor']==28
 assert all(a[k]is False for k in('price_writes','funding_writes','telegram_notifications','stock_writes'))
 def authority():assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(Cache(),WB());prior=io.get(ROOT+':execution')
 if prior:
  if prior['status']=='verified':print('Already verified; no replay');return
  raise ValueError('Existing execution retained; inspect, no blind repeat')
 e=dict(status='preflight',created_at=now(),ops={},wb_writes=0,price_writes=0,funding_writes=0,telegram_calls=0,model_calls=0,approval_key=ROOT+':approval');assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 orig=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json')
  ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  if u.hostname=='api.moysklad.ru':ok=m=='GET'and u.path.startswith('/api/remap/1.2/');time.sleep(.4)
  if u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  if u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config')or m=='POST'and u.path=='/api/advert/v1/bids/min'or (m,u.path,b)==allowed
  assert ok,'Outside one exact addition scope '+m+' '+str(u.hostname)+u.path
  return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.4);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=55)
  if not r.ok:raise ValueError('WB HTTP '+str(r.status_code)+' '+path)
  return r.json()if r.content else{}
 def camp():
  rows=req('/api/advert/v2/adverts?ids='+str(CID))['adverts'];assert len(rows)==1 and rows[0]['id']==CID;return rows[0]
 def write(key,path,body):
  nonlocal allowed
  authority();assert key not in e['ops'];e['ops'][key]=dict(status='submitting',path=path,body=body,submitted_at=now());save();allowed=('PATCH',path,body)
  try:r=req(path,'PATCH',body)
  except Exception:e['ops'][key]['status']='uncertain';save();raise
  finally:allowed=None
  e['ops'][key].update(status='accepted',response=r);e['wb_writes']+=1;save()
 def quote(ids):
  q=req('/api/advert/v1/bids/min','POST',dict(advert_id=CID,nm_ids=ids,payment_type='cpc',placement_types=['recommendation']))
  vals={n['nm_id']:next(b['value']for b in n['bids']if b['currency']=='CNY'and b['type']=='recommendation')for n in q['bids']};assert set(vals)==set(ids)and all(0<v<=28 for v in vals.values());return q
 try:
  c=camp();e['before']=c;save();assert c['currency']=='CNY'and c['status']==9 and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'and c['settings']['placements']==dict(search=False,recommendations=True)
  old={n['nm_id']:n for n in c['nm_settings']};assert len(old)==len(c['nm_settings'])and len(set(old)|{NM})<=50
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['cpcStep']==1 and cfg['cpcMaxBid']>=28
  prices=current_prices(io,[NM]);assert len(prices['rows'])==1;g=prices['rows'][0];assert g['article']==ART and g['seller_price']==445.92
  stock=Reader().stock([ART],'msk');assert stock['coverage_complete']and stock['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
  src=io.get('china_agent:advertising_full_growth:2026-11-25:v1:inputs:midday');assert src['status']=='complete'and src['cabinet']=='token_3'
  econ=model_rows(dict(products=src['own'],prices=prices,stock=stock,fx=src['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'));assert not econ['missing'];m=econ['rows'][str(NM)];assert m['stock_free']>0 and m['expected_margin_before_ads_cny']-.08*m['seller_price_cny']>0
  assert m['sample_size']==0 and m['buyout_fallback'] and .4*(m['seller_price_cny']*.72-m['own_cogs_rub']/float(src['fx']['rub_per_cny']))-m['logistics_cny']-.08*m['seller_price_cny']>0
  pub=published_stock(io,prices,[NM]);assert not pub['missing_nm_ids']and pub['amounts'][str(NM)]>0
  ref=NM if NM in old else next(n['nm_id']for n in c['nm_settings']if n['subject']['id']==50)
  q=quote([ref]);e.update(preflight=dict(prices=prices,stock=stock,published=pub,economics=econ,config=cfg,quote=q,observed_at=now()),status='running');save();assert norm(camp())==norm(c),'Campaign changed during checks'
  if NM not in old:
   assert c['restrictions']['can_change_nms'];write('add','/adv/v0/auction/nms',dict(nms=[dict(advert_id=CID,nms=dict(add=[NM],delete=[]))]))
  actual=None
  for _ in range(8):
   actual=camp();members={n['nm_id']:n for n in actual['nm_settings']}
   if set(members)==set(old)|{NM}and all(members[n]==v for n,v in old.items())and actual['settings']==c['settings']and actual['status']==c['status']:break
   time.sleep(3)
  else:raise ValueError('Composition readback mismatch; no replay')
  assert members[NM]['subject']['id']==50 and members[NM]['bids_kopecks']['search']==0
  e['exact_minimum']=quote([NM]);save();expected=copy.deepcopy(actual);n=next(n for n in expected['nm_settings']if n['nm_id']==NM)
  if n['bids_kopecks']['recommendations']!=28:
   assert norm(camp())==norm(actual);write('bid','/api/advert/v1/bids',dict(bids=[dict(advert_id=CID,nm_bids=[dict(nm_id=NM,bid_kopecks=28,placement='recommendations')])]))
  n['bids_kopecks']['recommendations']=28
  for _ in range(8):
   after=camp()
   if norm(after)==norm(expected)and norm(camp())==norm(expected):break
   time.sleep(3)
  else:raise ValueError('Whole campaign and bid readback mismatch')
  assert current_prices(io,[NM])['rows']==prices['rows'],'Price changed during addition'
  at=now();key=ROOT+':campaign:'+str(CID);rec=dict(status='verified',before=c,after=after,submitted_at=e['ops'].get('add',e['ops'].get('bid',{})).get('submitted_at',at),verified_at=at,authorization_key=ROOT+':approval',telegram_allowed=False,items=[dict(nm_id=NM,article=ART,placement='recommendations',target_minor=28,status='verified')]);assert io.create(key,rec)
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=key;io.put('china_agent:verified_campaign_state:v1',registry)
  from china_experiment_journal import receipt_changes
  changes=receipt_changes(key,rec,{NM:ART})
  for j,ch in enumerate(changes):
   event=dict(status='verified',record_type='verified_action',event_id='owner-seven-recovery25-add606-'+str(j),source_key=key,started_at=ch['at'],verified_at=at,action=dict(kind=ch['kind'],nm_ids=[NM],campaign_id=CID,article=ART,placement=ch.get('placement'),before=ch['before'],after=ch['after']),grants_action_permission=False,telegram_allowed=False);assert io.create('china_agent:experience:v1:owner-seven-recovery25-add606-'+str(j),event)
  for op in e['ops'].values():op['status']='verified'
  assert io.create(ROOT+':tracking',dict(status='active',execution_key=key,nm_id=NM,campaign_id=CID,bid_cny=.28,target_drr_pct=8,first_complete_msk_day='2026-11-26',first_early_review_msk_day='2026-11-27',auto_changes=False,auto_funding=False,new_monitor=False))
  e.update(status='verified',after=after,verified_at=at,receipt=key,reporting_registered=True);save()
 except Exception as ex:
  e.update(status='uncertain'if e['ops']else'blocked',reason=type(ex).__name__+': '+str(ex)[:250]);save();raise
 finally:requests.sessions.Session.request=orig
 print(json.dumps(dict(status=e['status'],nm_id=NM,campaign_id=CID,bid_cny=.28,wb_writes=e['wb_writes'],funding_writes=0,telegram_calls=0)))
if __name__=='__main__':main()

