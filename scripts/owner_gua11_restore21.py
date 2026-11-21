"""Restore only exact eleven owner-selected GUA products; no funding/Telegram."""
import copy,json,time,requests
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices
from china_moysklad_read import read_stock
from china_campaign_routes import guangzhou_models
ROOT='china_agent:owner_gua11_restore:2026-11-21:v1'
CID=41779660
ART={2128711871:'025',2128972258:'30',2128990207:'31',2129004929:'32',2129199358:'69',2129199359:'70',2129199361:'72',2129309883:'159',2129309886:'163',2129309887:'164',2129309888:'165'}
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO()
 if io.get(ROOT+':execution'):
  assert io.get(ROOT+':execution')['status']=='verified','Existing journal: no replay';print('Already verified');return
 a={'status':'approved','owner_id':5122667182,'campaign_id':CID,'nm_ids':sorted(ART),'instruction':'Return025,30,31,32,69,70,72,159,163,164,165 to test at minimum bid; no Telegram','telegram_send':False,'funding_authorized':False,'recorded_at':now()}
 if not io.get(ROOT+':approval'):assert io.create(ROOT+':approval',a)
 e=dict(status='preflight',created_at=now(),steps={},wb_writes=0,telegram_calls=0,model_calls=0)
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 orig=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);host=u.hostname or'';path=u.path;m=method.upper();body=kw.get('json')or{}
  if host=='api.telegram.org'or'openai'in host:raise ValueError('No Telegram/model')
  if host.endswith('moysklad.ru'):assert m=='GET'
  if host.endswith('wildberries.ru'):
   allowed=m=='GET'and path in('/api/advert/v2/adverts','/adv/v1/promotion/count','/api/advert/v1/config','/api/v2/list/goods/filter')or m=='POST'and path in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2373413','/content/v2/get/cards/list')
   if m=='PATCH'and path=='/adv/v0/auction/nms':allowed=body==e.get('add_body')
   if m=='PATCH'and path=='/api/advert/v1/bids':allowed=body==e.get('bid_body')
   assert allowed,'Outside exact owner restoration'
  return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None,host='advert-api.wildberries.ru'):
  time.sleep(1.2);r=requests.request(method,'https://'+host+path,headers={'Authorization':io.token},json=body,timeout=50);r.raise_for_status();return r.json()if r.content else{}
 def campaign():return req('/api/advert/v2/adverts?ids='+str(CID))['adverts'][0]
 def projection(c):return {k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')}
 def write(key,path,body):
  assert key not in e['steps']
  e['steps'][key]=dict(status='submitting',path=path,body=body,submitted_at=now());save()
  try:r=req(path,'PATCH',body)
  except Exception:e['steps'][key]['status']='uncertain';e['status']='uncertain';save();raise
  e['steps'][key].update(status='accepted',response=r);e['wb_writes']+=1;save()
 try:
  before=campaign();assert before['id']==CID and before['status']==9 and before['currency']=='CNY'and before['settings']['placements']=={'search':False,'recommendations':True}
  e['before']=before;e['before_budget']=req('/api/advert/v2/budget','POST',dict(advertIds=[CID]));cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
  old={n['nm_id']:n for n in before['nm_settings']};wanted=set(ART)-set(old)
  # Avoid adding a second live recommendation placement elsewhere.
  listing=req('/adv/v1/promotion/count');ids=sorted({x['advertId']for g in listing.get('adverts',[])for x in g.get('advert_list',[])})
  elsewhere={}
  for start in range(0,len(ids),50):
   for cp in req('/api/advert/v2/adverts?ids='+','.join(map(str,ids[start:start+50])))['adverts']:
    if cp['id']!=CID and cp['status']in(9,11) and cp['settings']['placements'].get('recommendations'):
     for n in cp['nm_settings']:
      if n['nm_id']in wanted:elsewhere.setdefault(n['nm_id'],[]).append(cp['id'])
  wanted-=set(elsewhere);e['already_in_campaign']=sorted(set(ART)&set(old));e['other_recommendation_campaigns']=elsewhere
  prices=current_prices(io,sorted(wanted));assert {p['nm_id']for p in prices['rows']}==wanted
  assert all(p['article'].split('-')[0]==ART[p['nm_id']]for p in prices['rows'])
  stock=read_stock([p['article']for p in prices['rows']],warehouse_role='guangzhou');assert stock['coverage_complete']
  cards=[]
  for nm in sorted(wanted):
   j=req('/content/v2/get/cards/list','POST',{'settings':{'cursor':{'limit':100},'filter':{'textSearch':str(nm),'withPhoto':-1}}},'content-api.wildberries.ru')
   found=[c for c in j['cards']if c['nmID']==nm];assert len(found)==1;cards.append({k:found[0].get(k)for k in('nmID','vendorCode','dimensions','sizes')})
  mapping={str(z['chrtID']):c['nmID']for c in cards for z in c['sizes']}
  pub=dict(warehouse_id=2373413,size_to_nm=mapping,raw=req('/api/v3/stocks/2373413','POST',{'chrtIds':[int(x)for x in mapping]},'marketplace-api.wildberries.ru'),observed_at=now())
  routes=io.get('china_agent:campaign_economics_routes:v1');route=copy.deepcopy(routes['campaigns'][str(CID)]);route['nm_ids']=sorted(wanted)
  inputs=io.get('china_agent:advertising_full_growth:2026-11-21:v1:inputs')
  evidence=dict(stock=stock,cards=dict(rows=cards,observed_at=now()),published=pub)
  models=guangzhou_models(dict(inputs,prices=prices),route,evidence,io.get('china_agent:new_ad_economics_policy:v1'))
  usable={int(n) for n,m in models['rows'].items()if m.get('stock_free',0)>0 and m.get('published_stock',0)>0}
  e['blocked_availability']={n:m for n,m in models['rows'].items()if int(n)not in usable}
  e['preflight']=dict(prices=prices,evidence=evidence,economics=models);save()
  assert usable,'No available requested products'
  # Owner-established equal category minimum; quote before membership with existing same-category representative.
  representative=next(n['nm_id']for n in before['nm_settings']if n['subject']['id']==50)
  q=req('/api/advert/v1/bids/min','POST',dict(advert_id=CID,nm_ids=[representative],payment_type='cpc',placement_types=['recommendation']))
  vals=[b['value']for row in q['bids']for b in row['bids']if b['type']=='recommendation'and b['currency']=='CNY'];assert len(vals)==1 and type(vals[0])is int and 0<vals[0]<=28
  minimum=vals[0];assert minimum%cfg['cpcStep']==0
  e.update(minimum_quote=q,target_minor=minimum,add_body=dict(nms=[dict(advert_id=CID,nms=dict(add=sorted(usable),delete=[]))]),status='running');save()
  assert projection(campaign())==projection(before),'Concurrent campaign changed'
  write('add','/adv/v0/auction/nms',e['add_body'])
  def verify(c,bids=False):
   assert c['status']==before['status']and c['currency']==before['currency']and c['settings']==before['settings']
   current={n['nm_id']:n for n in c['nm_settings']};assert set(current)==set(old)|usable
   assert all(current[n]==row for n,row in old.items()),'Existing member changed'
   assert all(current[n]['subject']['id']==50 for n in usable)
   if bids:assert all(current[n]['bids_kopecks']['recommendations']==minimum and current[n]['bids_kopecks'].get('search',0)==0 for n in usable)
   return c
  for attempt in range(10):
   try:added=verify(campaign());break
   except AssertionError:
    if attempt==9:raise
    time.sleep(3)
  e['steps']['add'].update(status='verified',after=added,verified_at=now());save()
  exact=req('/api/advert/v1/bids/min','POST',dict(advert_id=CID,nm_ids=sorted(usable),payment_type='cpc',placement_types=['recommendation']))
  exactmins={row['nm_id']:next(b['value']for b in row['bids']if b['type']=='recommendation'and b['currency']=='CNY')for row in exact['bids']}
  assert set(exactmins)==usable and all(v==minimum for v in exactmins.values());e['exact_minima']=exact
  bid_changes=[dict(nm_id=n,bid_kopecks=minimum,placement='recommendations')for n in sorted(usable)if next(x for x in added['nm_settings']if x['nm_id']==n)['bids_kopecks']['recommendations']!=minimum]
  if bid_changes:
   e['bid_body']=dict(bids=[dict(advert_id=CID,nm_bids=bid_changes)]);save();write('bids','/api/advert/v1/bids',e['bid_body'])
  for attempt in range(10):
   try:after=verify(campaign(),True);break
   except AssertionError:
    if attempt==9:raise
    time.sleep(3)
  time.sleep(3);after2=verify(campaign(),True)
  if 'bids'in e['steps']:e['steps']['bids'].update(status='verified',after=after2,verified_at=now())
  e.update(status='verified',after=after2,readbacks=[after,after2],added_nm_ids=sorted(usable),verified_at=now());save()
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=ROOT+':execution';io.put('china_agent:verified_campaign_state:v1',registry)
  # Preserve route identity and all actual members for normal future reports.
  routes['campaigns'][str(CID)].update(nm_ids=sorted(set(old)|usable),composition_receipt=ROOT+':execution');io.put('china_agent:campaign_economics_routes:v1',routes)
  previous=io.get('china_agent:campaign_route_cards:v1:'+str(CID))or{}
  allcards={c['nmID']:c for c in previous.get('rows',[])};allcards.update({c['nmID']:c for c in cards})
  assert set(old)|usable<=set(allcards)
  io.put('china_agent:campaign_route_cards:v1:'+str(CID),dict(rows=[allcards[n]for n in sorted(set(old)|usable)],observed_at=now()))
  e['reports_registered']=True;save()
 except Exception as ex:
  if e['status']!='verified':e.update(status='uncertain'if any(s['status']in('submitting','accepted','uncertain')for s in e['steps'].values())else'blocked',error=type(ex).__name__+': '+str(ex)[:250]);save()
  raise
 print(json.dumps(dict(status=e['status'],added=len(e['added_nm_ids']),blocked=list(e['blocked_availability']),minimum=minimum,wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()
