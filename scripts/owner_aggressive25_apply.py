"""Exact twenty approved bid raises only. No deposits, composition, prices, TG or model."""
import json,copy,time,hashlib,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices,published_stock
ROOT='china_agent:owner_aggressive25:v1'
def now():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','bid_type','settings','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');p=io.get(ROOT+':plan');items=p['established_placement_raises']+p['new_search_test_raises']
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['plan_sha256']==digest(p)and a['funding_writes']is False and a['price_changes']is False and a['telegram_send']is False
 assert len(items)==20 and len({(x['cid'],x['nm'])for x in items})==20 and all(x['target_minor']>x['current_minor']for x in items)
 def authority():assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(Cache(),WB());prior=io.get(ROOT+':execution')
 if prior:
  if prior['status']=='verified':print('Verified execution retained; no replay');return
  raise ValueError('Existing execution must be inspected, no blind retry')
 e=dict(status='preflight',created_at=now(),approval_key=ROOT+':approval',plan_sha256=digest(p),ops={},campaigns={},wb_writes=0,funding_writes=0,price_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json')
  ok=u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config')or m=='POST'and u.path=='/api/advert/v1/bids/min'or m=='PATCH'and u.path=='/api/advert/v1/bids'and b==allowed
  if u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  if u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  assert ok,'Exact bid-only authorization; request rejected '+m+' '+str(u.hostname)+u.path
  return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=55)
  if not r.ok:raise ValueError('WB read/write HTTP '+str(r.status_code)+' '+path)
  return r.json()if r.content else{}
 def campaign(cid):
  c=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(c)==1 and c[0]['id']==cid and c[0]['currency']=='CNY';return c[0]
 def verify(cid,expected):
  for _ in range(9):
   c=campaign(cid)
   if norm(c)==norm(expected):
    second=campaign(cid)
    if norm(second)==norm(expected):return second
   time.sleep(3)
  raise ValueError('Whole campaign readback mismatch '+str(cid))
 try:
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['cpcStep']==1
  nms=sorted({x['nm']for x in items});prices=current_prices(io,nms);mapping={x['nm_id']:x for x in prices['rows']};econ=io.get('china_agent:owner_sales_revival:2026-11-25:v1:approval')['economics']
  for x in items:
   g=mapping[x['nm']];m=econ[str(x['nm'])];assert g['article']==x['article']and abs(g['seller_price']-m['price'])<.001 and m['margin']-.08*m['price']>0
  # Reuse the proved MSK store snapshot; actual availability is freshly checked in WB.
  stock=io.get('china_agent:advertising_full_growth:2026-11-25:v1:inputs')['stock'];assert stock['coverage_complete']and stock['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'and(datetime.now(timezone.utc)-datetime.fromisoformat(stock['observed_at'])).total_seconds()<8*3600
  for g in mapping.values():
   rs=[r for r in stock['rows']if r['article'].casefold()==g['article'].casefold()];assert len(rs)==1 and rs[0]['stock']-rs[0]['reserve']>0
  pub=published_stock(io,prices,nms);assert not pub['missing_nm_ids']and all(pub['amounts'][str(n)]>0 for n in nms)
  ids=sorted({x['cid']for x in items});before={cid:campaign(cid)for cid in ids};protected={cid:campaign(cid)for cid in(42088552,42022679)}
  minima={}
  for cid in ids:
   chosen=[x for x in items if x['cid']==cid];c=before[cid];assert c['status']==9 and c['settings']['payment_type']=='cpc'and c['bid_type']=='manual'
   zone=chosen[0]['placement'];assert all(x['placement']==zone for x in chosen)and c['settings']['placements']==dict(search=zone=='search',recommendations=zone=='recommendations')
   members={n['nm_id']:n for n in c['nm_settings']};assert len(members)==len(c['nm_settings'])
   q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=sorted(x['nm']for x in chosen),payment_type='cpc',placement_types=['search'if zone=='search'else'recommendation']))
   mins={r['nm_id']:next(b['value']for b in r['bids']if b['currency']=='CNY'and b['type']==('search'if zone=='search'else'recommendation'))for r in q['bids']};assert set(mins)=={x['nm']for x in chosen};minima[str(cid)]=q
   for x in chosen:assert x['nm']in members and members[x['nm']]['bids_kopecks'][zone]in(x['current_minor'],x['target_minor'])and mins[x['nm']]<=x['target_minor']<=cfg['cpcMaxBid']
  e['preflight']=dict(prices=prices,stock_reference='china_agent:advertising_full_growth:2026-11-25:v1:inputs',stock_observed_at=stock['observed_at'],published=pub,campaigns={str(k):v for k,v in before.items()},protected={str(k):v for k,v in protected.items()},minima=minima,observed_at=now());e['status']='running';save()
  for cid in ids:
   authority();start=campaign(cid);assert norm(start)==norm(before[cid]);expected=copy.deepcopy(start);bids=[];chosen=[x for x in items if x['cid']==cid]
   for x in chosen:
    n=next(n for n in expected['nm_settings']if n['nm_id']==x['nm'])
    if n['bids_kopecks'][x['placement']]!=x['target_minor']:bids.append(dict(nm_id=x['nm'],bid_kopecks=x['target_minor'],placement=x['placement']));n['bids_kopecks'][x['placement']]=x['target_minor']
   if bids:
    body=dict(bids=[dict(advert_id=cid,nm_bids=bids)]);key=str(cid)+':bids';assert key not in e['ops'];e['ops'][key]=dict(status='submitting',request=body,submitted_at=now());save();allowed=body
    try:response=req('/api/advert/v1/bids','PATCH',body)
    except Exception:e['ops'][key]['status']='uncertain';save();raise
    finally:allowed=None
    e['ops'][key].update(status='accepted',response=response);e['wb_writes']+=1;save()
   after=verify(cid,expected);rec=dict(status='verified',before=start,after=after,items=[dict(x,status='verified')for x in chosen],verified_at=now(),authorization_key=ROOT+':approval')
   receipt=ROOT+':campaign:'+str(cid);assert io.create(receipt,rec);registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=receipt;io.put('china_agent:verified_campaign_state:v1',registry)
   e['campaigns'][str(cid)]=dict(status='verified',receipt=receipt,after=after,items=len(chosen));
   if bids:e['ops'][key]['status']='verified'
   save()
  final={cid:campaign(cid)for cid in ids};assert all(norm(final[cid])==norm(e['campaigns'][str(cid)]['after'])for cid in ids)
  assert all(norm(campaign(cid))==norm(c)for cid,c in protected.items())
  finalprices=current_prices(io,nms);assert sorted(finalprices['rows'],key=lambda r:r['nm_id'])==sorted(prices['rows'],key=lambda r:r['nm_id'])
  track=io.get('china_agent:bid_raise_tracking:v1')or{'items':{}}
  for x in items:track.setdefault('items',{})[str(x['cid'])+':'+str(x['nm'])]=dict(status='active',plan=x,started_at=e['created_at'],verified_at=now(),execution_key=ROOT+':campaign:'+str(x['cid']),target_drr_pct=8,first_complete_msk_day='2026-11-26',first_early_review_msk_day='2026-11-27',auto_revert_authorized=False)
  io.put('china_agent:bid_raise_tracking:v1',track)
  assert io.create(ROOT+':tracking',dict(status='active',items=items,target_drr_pct=8,execution_key=ROOT+':execution',source_read_key=ROOT+':read',existing_hourly_collector=True,new_monitor=False,auto_changes=False,auto_funding=False,first_complete_msk_day='2026-11-26',first_early_review_msk_day='2026-11-27'))
  e.update(status='verified',completed_at=now(),verified_items=20,prices_unchanged_verified=True,protected_unchanged_verified=True,reporting_registered=True,final_campaigns={str(k):v for k,v in final.items()});save()
 except Exception as ex:
  e.update(status='uncertain'if any(x['status']in('submitting','accepted','uncertain')for x in e['ops'].values())else'partial'if e['wb_writes']else'blocked',reason=type(ex).__name__+': '+str(ex)[:240]);save();raise
 finally:requests.sessions.Session.request=original
 print(json.dumps(dict(status=e['status'],items=20,wb_writes=e['wb_writes'],funding_writes=0,telegram_calls=0)))
if __name__=='__main__':main()