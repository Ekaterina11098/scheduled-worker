"""Owner exact018 recommendation CPC addition; no funding/price/TG/model calls."""
import copy,json,time,requests,os
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
ROOT='china_agent:owner_add018:2026-11-25:v1'
NM=2344552267
ARTICLE='018-JuneBag-black'
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):return dict(id=c['id'],status=c['status'],settings=c['settings'],currency=c['currency'],bid_type=c['bid_type'],nm_settings=sorted(c['nm_settings'],key=lambda n:n['nm_id']))
def main():
 io=AdvertisingIO();auth=io.get(ROOT+':approval');assert auth['status']=='approved'and auth['owner_id']==5122667182 and auth['nm_id']==NM and auth['placement']=='recommendations'and auth['funding_allowed']is False
 e=io.get(ROOT+':execution')
 if e:
  if e['status']=='verified':print('Already verified; no replay');return
  raise ValueError('Existing attempt; inspect exact journal before continuation')
 e=dict(status='preflight',created_at=now(),wb_writes=0,telegram_calls=0,model_calls=0,ops={},approval_key=ROOT+':approval')
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 orig=requests.sessions.Session.request;allowed=None
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path+('?' +u.query if u.query else'')
  if (u.hostname or'').endswith('wildberries.ru'):
   if m in('PATCH','PUT','DELETE')or(m=='POST'and u.path not in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2126188','/content/v2/get/cards/list'))or u.path in('/adv/v0/start','/adv/v0/stop','/adv/v0/pause'):
    assert allowed==(m,path,kw.get('json')),'Outside exact journalled addition'
  elif (u.hostname or'').endswith('moysklad.ru'):assert m=='GET'
  else:assert u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname,'No Telegram/model/other traffic'
  return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=(10,55));assert r.ok,'WB HTTP '+str(r.status_code);return r.json()if r.content else {}
 def camp(cid):
  rows=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(rows)==1 and rows[0]['id']==cid;return rows[0]
 def write(name,path,body):
  nonlocal allowed
  assert name not in e['ops'],'Submitted write is never repeated'
  e['ops'][name]=dict(status='submitting',method='PATCH',path=path,body=body,submitted_at=now());save();allowed=('PATCH',path,body)
  try:response=req(path,'PATCH',body)
  except Exception:
   e['ops'][name]['status']='uncertain';save();raise
  finally:allowed=None
  e['wb_writes']+=1;e['ops'][name].update(status='accepted',response=response);save()
 try:
  prices=current_prices(io,[NM]);assert prices['rows'][0]['article'].casefold()==ARTICLE.casefold()
  stock=read_stock([ARTICLE],warehouse_role='msk');pub=published_stock(io,prices,[NM])
  assert stock['coverage_complete']and stock['rows'][0]['stock']-stock['rows'][0]['reserve']>0 and pub['amounts'].get(str(NM),0)>0,'No current available MSK/published stock'
  count=req('/adv/v1/promotion/count');ids=sorted({a['advertId']for g in count.get('adverts',[])if g['status']in(9,11)for a in g.get('advert_list',[])})
  assert 0<len(ids)<100
  campaigns=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts'];assert {c['id']for c in campaigns}==set(ids)
  protected=next(c for c in campaigns if c['id']==42088552)
  existing=[c for c in campaigns if any(n['nm_id']==NM for n in c['nm_settings'])]
  e.update(prices=prices,stock=stock,published=pub,campaigns_before=campaigns,existing_campaign_ids=[c['id']for c in existing]);save()
  assert not existing,'Already present in another active/paused campaign; do not duplicate'
  eligible=[c for c in campaigns if c['id']!=42088552 and c['status']==9 and c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'and c['settings']['placements'].get('recommendations')is True and c['settings']['placements'].get('search')is False and c.get('restrictions',{}).get('can_change_nms')and 0<len(c['nm_settings'])<50 and {n['subject']['id']for n in c['nm_settings']}=={50}]
  order={40933588:0,41270309:1,41055480:2};eligible.sort(key=lambda c:(order.get(c['id'],10),len(c['nm_settings']),c['id']))
  assert eligible,'No active recommendation CPC bag campaign with capacity'
  before=eligible[0];cid=before['id'];representative=before['nm_settings'][0]['nm_id']
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
  q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=[representative],payment_type='cpc',placement_types=['recommendation']))
  vals=[b['value']for r in q['bids']if r['nm_id']==representative for b in r['bids']if b['type']=='recommendation'and b['currency']=='CNY'];assert len(vals)==1 and type(vals[0])is int and vals[0]>0
  target=vals[0];assert target%cfg['cpcStep']==0 and target<=cfg['cpcMaxBid']
  e.update(campaign_id=cid,before=before,minimum_quote=q,bid_minor=target,minimum_basis='same_subject_cpc_placement_owner_verified_v1');save()
  assert norm(camp(cid))==norm(before),'Composition changed before addition'
  write('add','/adv/v0/auction/nms',dict(nms=[dict(advert_id=cid,nms=dict(add=[NM],delete=[]))]))
  current=None
  for _ in range(8):
   current=camp(cid)
   if {n['nm_id']for n in current['nm_settings']}=={n['nm_id']for n in before['nm_settings']}|{NM}:break
   time.sleep(5)
  assert len(current['nm_settings'])==len(before['nm_settings'])+1
  assert current['status']==before['status']and current['settings']==before['settings']
  old={n['nm_id']:n for n in before['nm_settings']};actual={n['nm_id']:n for n in current['nm_settings']}
  assert set(actual)==set(old)|{NM}and all(actual[k]==v for k,v in old.items())
  added=actual[NM];assert added['subject']['id']==50 and added['bids_kopecks'].get('search',0)==0
  exact=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=[NM],payment_type='cpc',placement_types=['recommendation']))
  v=[b['value']for r in exact['bids']if r['nm_id']==NM for b in r['bids']if b['type']=='recommendation'and b['currency']=='CNY'];assert v==[target],'Exact new-member minimum differs; no bid change'
  e['exact_minimum']=exact;save()
  if added['bids_kopecks'].get('recommendations')!=target:
   write('bid','/api/advert/v1/bids',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=NM,placement='recommendations',bid_kopecks=target)])]))
  expected=copy.deepcopy(before);added=copy.deepcopy(added);added['bids_kopecks']['recommendations']=target;expected['nm_settings'].append(added)
  e['readbacks']=[]
  for _ in range(2):
   after=camp(cid);assert norm(after)==norm(expected),'Full package readback changed';e['readbacks'].append(after);save()
  assert norm(camp(42088552))==norm(protected),'Protected campaign changed'
  e.update(status='verified',after=after,verified_at=now());e['ops']={k:dict(v,status='verified')for k,v in e['ops'].items()};save()
  receipt=ROOT+':campaign:'+str(cid);assert io.create(receipt,dict(status='verified',after=after,verified_at=e['verified_at'],parent=ROOT+':execution'))
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=receipt;io.put('china_agent:verified_campaign_state:v1',registry)
  tracking=io.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={});day=datetime.now(ZoneInfo('Europe/Moscow')).date()
  tracking.setdefault('plans',{})['owner-add018-25']=dict(status='active',campaign_ids=[cid],started_at=e['verified_at'],nm_ids=[NM],bid_minor=target,placement='recommendations',execution_key=receipt,auto_topup=False,existing_reports=True,evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))))
  if io.get('china_agent:new_ad_tests:tracking:v1'):io.put('china_agent:new_ad_tests:tracking:v1',tracking)
  else:assert io.create('china_agent:new_ad_tests:tracking:v1',tracking)
  e['reports_registered']=True;save()
 except Exception as ex:
  e.update(status='uncertain'if e['wb_writes']or any(v['status']in('submitting','accepted','uncertain')for v in e['ops'].values())else'blocked',error=str(ex)[:250]);save();raise
 print(json.dumps(dict(status=e['status'],campaign_id=e['campaign_id'],bid_cny=e['bid_minor']/100,wb_writes=e['wb_writes'],price=prices['rows'][0]['seller_price'],published=pub['amounts'][str(NM)],free=stock['rows'][0]['stock']-stock['rows'][0]['reserve'])))
if __name__=='__main__':main()
