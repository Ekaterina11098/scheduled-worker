"""Exact private owner bid change; one mutation journal, no Telegram/model."""
import copy,json,time,requests
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices,published_stock
ROOT='china_agent:fur_bid_raise:2026-11-20:v2'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a['owner_id']==5122667182 and a['status']=='approved'
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 cid=a['campaign_id'];ids=sorted(map(int,a['targets']));before=None
 old=io.get(ROOT+':execution')
 if old:
  assert old['status']=='verified','Existing journal: read-only recovery required';return
 e=dict(status='preflight',created_at=now(),wb_writes=0,telegram_calls=0,model_calls=0,approval_key=ROOT+':approval')
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 original=requests.sessions.Session.request
 body=dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=n,bid_kopecks=a['targets'][str(n)],placement='recommendations')for n in ids])])
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);host=u.hostname or '';p=u.path;m=method.upper()
  assert 'telegram'not in host and 'openai'not in host
  if host.endswith('wildberries.ru'):
   allowed=m=='GET'and p in('/api/advert/v2/adverts','/api/v2/list/goods/filter')
   allowed=allowed or m=='POST'and p in('/api/advert/v1/bids/min','/api/v3/stocks/2126188')
   allowed=allowed or m=='PATCH'and p=='/api/advert/v1/bids'and kw.get('json')==body
   assert allowed,'Unapproved marketplace request'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def campaign():
  cs=http(io,'/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(cs)==1 and cs[0]['id']==cid
  return cs[0]
 def stable(c):return {k:c[k]for k in('id','status','currency','bid_type','settings','nm_settings')}
 try:
  validate_identity(Cache(),WB())
  before=campaign();e['before']=before;save()
  assert before['status']==9 and before['currency']=='CNY'and before['settings']['placements']==dict(search=False,recommendations=True)
  reference=io.get(a['review_key']);assert reference['status']=='complete'
  assert {n['nm_id']for n in before['nm_settings']}=={n['nm_id']for n in reference['campaign']['nm_settings']}
  expected=copy.deepcopy(before)
  for n in expected['nm_settings']:
   if n['nm_id']in ids:
    assert n['bids_kopecks']['recommendations']==a['before_bid_minor']and n['bids_kopecks']['search']==0
    n['bids_kopecks']['recommendations']=a['targets'][str(n['nm_id'])]
   else:assert n['bids_kopecks']['recommendations']==a['preserved_bid_minor']
  prices=current_prices(io,ids);e['prices']=prices
  assert all(r['seller_price']==reference['economics']['rows'][str(r['nm_id'])]['seller_price_cny']for r in prices['rows'])and len(prices['rows'])==len(ids)
  stock=published_stock(io,prices,ids);e['published_stock']=stock;assert all(stock['amounts'].get(str(n),0)>0 for n in ids)
  minimum=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=ids,payment_type='cpc',placement_types=['recommendation']));e['minimum']=minimum
  assert {n['nm_id']for n in minimum['bids']}==set(ids)
  assert all(any(b['type']=='recommendation'and b['currency']=='CNY'and 0<b['value']<=a['targets'][str(n['nm_id'])]for b in n['bids'])for n in minimum['bids'])
  e['step']=dict(status='submitting',request=body,submitted_at=now());save()
  try:
   r=requests.patch('https://advert-api.wildberries.ru/api/advert/v1/bids',headers={'Authorization':io.token},json=body,timeout=50);r.raise_for_status();response=r.json()if r.content else{}
  except Exception:
   e['step']['status']='uncertain';e['status']='uncertain';save();raise
  e['wb_writes']=1;e['step'].update(status='accepted',response=response);save()
  for i in range(12):
   actual=campaign()
   if stable(actual)==stable(expected):break
   if i==11:raise AssertionError('Exact readback mismatch; do not repeat PATCH')
   time.sleep(5)
  time.sleep(3);after=campaign();assert stable(after)==stable(expected),'Second readback mismatch'
  e.update(status='verified',after=after,verified_at=now());e['step']['status']='verified';save()
  registry=io.get('china_agent:verified_campaign_state:v1')or {};registry[str(cid)]=ROOT+':execution';io.put('china_agent:verified_campaign_state:v1',registry)
  tracking=io.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={});day=datetime.now(ZoneInfo('Europe/Moscow')).date()
  tracking.setdefault('plans',{})['owner-fur57-bid-20261120']=dict(status='active',campaign_ids=[cid],execution_key=ROOT+':execution',started_at=e['verified_at'],existing_reports=True,items=[dict(skus=[dict(nm_id=n,bid_minor=a['targets'][str(n)])for n in ids])],evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))),auto_topup=False)
  io.put('china_agent:new_ad_tests:tracking:v1',tracking)
  e['reports_registered']=True;save()
 except Exception as ex:
  if e.get('status')!='verified':e['status']='uncertain'if e.get('step',{}).get('status')in('submitting','accepted','uncertain')else'blocked'
  e['error']=str(ex)[:500];save();raise
 print(json.dumps(dict(status=e['status'],wb_writes=e['wb_writes'])))
if __name__=='__main__':main()
