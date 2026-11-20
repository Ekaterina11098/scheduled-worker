"""Frozen owner-approved multi-campaign launch. Journal every mutation once; no Telegram/model."""
import copy,json,time,os,requests,math
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse,parse_qs
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
from china_campaign_routes import guangzhou_models
from china_loss_control import digest
ROOT='china_agent:owner_extra73_launch:2026-11-20:v1'
def now():return datetime.now(timezone.utc).isoformat()
def check(c,g,status,bids=False):
 zone=g['placement'];ids=set(g['nm_ids']);other='search'if zone=='recommendations'else'recommendations'
 assert c['status']==status and c['currency']=='CNY'and c['bid_type']=='manual'
 assert c['settings']['name']==g['name']and c['settings']['payment_type']=='cpc'
 assert c['settings']['placements']=={'search':zone=='search','recommendations':zone=='recommendations'}
 assert {n['nm_id']for n in c['nm_settings']}==ids and len(c['nm_settings'])==len(ids)
 assert all(n['subject']['id']==g['subject_id']for n in c['nm_settings'])
 if bids:assert all(n['bids_kopecks'].get(zone)==g['bid_minor']and n['bids_kopecks'].get(other,0)==0 for n in c['nm_settings'])
 return c
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a['status']=='approved'and a['owner_id']==5122667182 and a['telegram_send']is False
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])and a['groups_sha256']==digest(a['groups'])
 assert (io.get('china_agent:owner_funding20_repair:v1:execution')or{}).get('status')=='verified','First finish remaining confirmed funding'
 assert sum(len(g['nm_ids'])for g in a['groups'])==73 and sum(g['amount_cny']for g in a['groups'])==2000
 allids=[n for g in a['groups']for n in g['nm_ids']];assert len(set(allids))==len(allids)
 previous=io.get(ROOT+':execution')
 if previous:
  assert previous['status']=='verified','Existing execution: inspect receipts; never replay';print('Already verified');return
 e=dict(status='preflight',groups=[],created_at=now(),approval_key=ROOT+':approval',wb_writes=0,telegram_calls=0,model_calls=0)
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or'';path=u.path;body=kw.get('json')or{}
  if host=='api.telegram.org'or'openai'in host:raise ValueError('No Telegram or paid model')
  if host.endswith('moysklad.ru'):assert m=='GET','No stock writes'
  if host.endswith('wildberries.ru'):
   allowed=m=='GET'and path in('/api/advert/v1/config','/adv/v1/balance','/adv/v1/promotion/count','/api/advert/v2/adverts','/api/v2/list/goods/filter')or m=='POST'and path in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2126188','/api/v3/stocks/2373413')
   owned={s.get('campaign_id')for s in e['groups']if s.get('campaign_id')}
   if path=='/adv/v2/seacat/save-ad'and m=='POST':allowed=any(body==dict(name=g['name'],nms=sorted(g['nm_ids']),bid_type='manual',payment_type='cpc',placement_types=[g['placement']])for g in a['groups'])
   if path=='/api/advert/v1/bids'and m=='PATCH':
    allowed=bool(body.get('bids'))
    for b in body.get('bids',[]):
     state=next((s for s in e['groups']if s.get('campaign_id')==b['advert_id']),None)
     if not state:allowed=False;continue
     spec=a['groups'][state['group_index']]
     allowed=allowed and b['nm_bids']==[dict(nm_id=n,bid_kopecks=spec['bid_minor'],placement=spec['placement'])for n in sorted(spec['nm_ids'])]
   if path=='/adv/v1/budget/deposit'and m=='POST':
    cid=int(parse_qs(u.query)['id'][0]);state=next((s for s in e['groups']if s.get('campaign_id')==cid),None)
    allowed=bool(state)and body.get('sum')==a['groups'][state['group_index']]['amount_cny']and body.get('type')in(0,1)
   if path=='/adv/v0/start'and m=='GET':allowed=int(parse_qs(u.query)['id'][0])in owned
   assert allowed,'Outside exact approved launch transport'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 validate_identity(Cache(),WB())
 def req(path,method='GET',body=None):
  time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50);r.raise_for_status();return r.json()if r.content else{}
 def listing():
  j=req('/adv/v1/promotion/count');ids=sorted({r['advertId']for group in j.get('adverts',[])for r in group.get('advert_list',[])})
  states=[]
  for i in range(0,len(ids),50):states+=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids[i:i+50])))['adverts']
  return states
 def campaign(cid):
  rows=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(rows)==1 and rows[0]['id']==cid;return rows[0]
 def budget(cid):
  rows=req('/api/advert/v2/budget','POST',dict(advertIds=[cid]))['adverts'];assert len(rows)==1 and rows[0]['advertId']==cid
  assert rows[0].get('currency')=='CNY'or rows[0]['total']==0 and rows[0].get('currency')in('',None)
  return rows[0]['total']
 def wait(fn):
  for i in range(15):
   try:return fn()
   except (AssertionError,ValueError):
    if i==14:raise
    time.sleep(5)
 def write(state,step,path,method,body=None):
  assert step not in state['steps'],'Do not repeat any submitted mutation'
  assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
  state['steps'][step]=dict(status='submitting',request=dict(path=path,method=method,body=body),submitted_at=now());save()
  try:r=req(path,method,body)
  except Exception:state['steps'][step]['status']='uncertain';state['status']='uncertain';e['status']='uncertain';save();raise
  state['steps'][step].update(status='accepted',response=r);e['wb_writes']+=1;save();return r
 def verified(state,step,readback):state['steps'][step].update(status='verified',readback=readback,verified_at=now());save()
 try:
  cfg=req('/api/advert/v1/config');wallet=req('/adv/v1/balance');assert cfg['currency']==wallet['currency']=='CNY'
  source=0 if wallet.get('balance',0)>=2000 else 1 if wallet.get('net',0)>=2000 else None;assert source is not None,'Insufficient wallet for approved total'
  states=listing();names={g['name']for g in a['groups']};assert not any(c['status']!=7 and c['settings']['name']in names for c in states),'Matching campaign exists; reconcile instead of create'
  assert not any(set(allids)&{n['nm_id']for n in c['nm_settings']}for c in states if c['status']in(9,11)),'Approved SKU now has another active/paused campaign'
  e['preexisting_campaign_ids']=sorted(c['id']for c in states);save()
  prices=current_prices(io,allids);current={r['nm_id']:r for r in prices['rows']};old=io.get('china_agent:advertising_full_growth:2026-11-20:v1:inputs')
  policy=io.get('china_agent:new_ad_economics_policy:v1');delivery=io.get('china_agent:expected_profit_delivery_model:v1')
  msk_ids={n for g in a['groups']if g['warehouse']=='msk'for n in g['nm_ids']}
  msk_prices=dict(prices,rows=[p for p in prices['rows']if p['nm_id']in msk_ids]);stock=read_stock([p['article']for p in msk_prices['rows']],warehouse_role='msk')
  pub=published_stock(io,msk_prices,sorted(msk_ids));assert stock['coverage_complete']and not pub['missing_nm_ids']
  models=model_rows(dict(products=old['own'],prices=msk_prices,stock=stock,fx=old['fx']),policy,delivery)
  assert not models['missing']and set(models['rows'])==set(map(str,msk_ids))
  for n,m in models['rows'].items():m.update(published_stock=pub['amounts'][n],published_stock_observed_at=pub['observed_at'],warehouse_role='msk',fx_rub_per_cny=old['fx']['rub_per_cny'],fx_date=old['fx'].get('date'))
  gua_evidence=io.get('china_agent:extra_advertising:2026-11-20:v1:guangzhou');route=copy.deepcopy(gua_evidence['route'])
  gua_ids={n for g in a['groups']if g['warehouse']=='guangzhou'for n in g['nm_ids']}
  gp=dict(prices,rows=[p for p in prices['rows']if p['nm_id']in gua_ids]);gs=read_stock([p['article']for p in gp['rows']],warehouse_role='guangzhou')
  cards=dict(gua_evidence['cards'],rows=[c for c in gua_evidence['cards']['rows']if c['nmID']in gua_ids]);assert {c['nmID']for c in cards['rows']}==gua_ids
  mapping={str(sz):p['nm_id']for p in gp['rows']for sz in p['size_ids']};r=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/'+str(route['published_warehouse_id']),headers={'Authorization':io.token},json=dict(chrtIds=list(map(int,mapping))),timeout=50);r.raise_for_status()
  ge=dict(stock=gs,cards=cards,published=dict(warehouse_id=route['published_warehouse_id'],size_to_nm=mapping,raw=r.json(),observed_at=now()))
  route['nm_ids']=sorted(gua_ids);gm=guangzhou_models(dict(old,prices=prices),route,ge,policy);models['rows'].update(gm['rows'])
  proposal=io.get(a['proposal_key']);rows={r['nm_id']:r for r in proposal['rows']}
  for nm in allids:
   m=models['rows'][str(nm)];pr=current[nm];baseline=rows[nm]
   assert pr['article']==baseline['article']and pr['seller_price']==baseline['price'],'Approved SKU/price changed'
   assert m['expected_margin_before_ads_cny']-pr['seller_price']*.05>0,'Current model no longer positive at target DRR'
   assert m['stock_free']>0 and m['published_stock']>0,'Current availability missing'
   spec=next(g for g in a['groups']if nm in g['nm_ids']);need=math.ceil(baseline['orders_3d']+90*spec['bid_minor']/100/(pr['seller_price']*.05))
   assert min(m['stock_free'],m['published_stock'])>=need,'Three-day stock reference no longer covered: '+pr['article']
  e.update(preflight=dict(prices=prices,stock_msk=stock,published_msk=pub,guangzhou=ge,economics=models,config=cfg),status='running');save()
  for index,g in enumerate(a['groups']):
   assert cfg['minTopUp']<=g['amount_cny']*100 and g['bid_minor']%cfg['cpcStep']==0 and g['bid_minor']<=cfg['cpcMaxBid']
   state=dict(group_index=index,name=g['name'],status='preflight',steps={});e['groups'].append(state);save()
   q=io.get(g['minimum_quote_key'])
   kind='search'if g['placement']=='search'else'recommendation'
   minimum=req('/api/advert/v1/bids/min','POST',dict(advert_id=q['campaign_id'],nm_ids=[q['nm_id']],payment_type='cpc',placement_types=[kind]))
   vals=[b['value']for n in minimum['bids']for b in n['bids']if b['type']==kind and b['currency']=='CNY'];assert len(vals)==1 and 0<vals[0]<=g['bid_minor']
   state['minimum_before']=minimum;save()
   response=write(state,'create','/adv/v2/seacat/save-ad','POST',dict(name=g['name'],nms=sorted(g['nm_ids']),bid_type='manual',payment_type='cpc',placement_types=[g['placement']]))
   cid=response if type(response)is int else response.get('advertId')if isinstance(response,dict)else None;assert type(cid)is int and cid>0
   state['campaign_id']=cid;save();draft=wait(lambda:check(campaign(cid),g,4));state['before']=draft;verified(state,'create',draft)
   exact=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=sorted(g['nm_ids']),payment_type='cpc',placement_types=[kind]))
   mins={n['nm_id']:next(b['value']for b in n['bids']if b['currency']=='CNY'and b['type']==kind)for n in exact['bids']};assert set(mins)==set(g['nm_ids'])and all(0<v<=g['bid_minor']for v in mins.values());state['exact_minima']=exact;save()
   write(state,'bids','/api/advert/v1/bids','PATCH',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=n,bid_kopecks=g['bid_minor'],placement=g['placement'])for n in sorted(g['nm_ids'])])]))
   verified(state,'bids',wait(lambda:check(campaign(cid),g,4,True)))
   initial=budget(cid);assert initial==0;state['before_budget']=initial;save()
   write(state,'fund','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=g['amount_cny'],type=source))
   def funded():
    b=budget(cid);assert b==g['amount_cny'];return b
   state['funded_budget']=wait(funded);verified(state,'fund',state['funded_budget'])
   check(campaign(cid),g,4,True)
   write(state,'start','/adv/v0/start?id='+str(cid),'GET')
   after=wait(lambda:check(campaign(cid),g,9,True));verified(state,'start',after)
   state.update(status='verified',after=after,after_budget=budget(cid),funding_cny=g['amount_cny'],verified_at=now());save()
   child=ROOT+':campaign:'+str(cid);assert io.create(child,copy.deepcopy(state))
   registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=child;io.put('china_agent:verified_campaign_state:v1',registry)
   if g['warehouse']=='guangzhou':
    routes=io.get('china_agent:campaign_economics_routes:v1');newroute=copy.deepcopy(route);newroute['nm_ids']=sorted(g['nm_ids']);newroute.update(composition_receipt=child,grants_action_permission=False,selling_route_change=False);routes['campaigns'][str(cid)]=newroute;io.put('china_agent:campaign_economics_routes:v1',routes)
    assert io.create('china_agent:campaign_route_cards:v1:'+str(cid),cards)
   tracking=io.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={});day=datetime.fromisoformat(state['verified_at']).astimezone(ZoneInfo('Europe/Moscow')).date()
   tracking.setdefault('plans',{})['owner-extra73-20261120-group'+str(index)]=dict(status='active',campaign_ids=[cid],started_at=state['verified_at'],execution_key=child,budget_cny=g['amount_cny'],items=[dict(name=g['name'],payment_type='cpc',bid_type='manual',placements=[g['placement']],budget_cny=g['amount_cny'],auto_topup=False,skus=[dict(nm_id=n,bid_minor=g['bid_minor'])for n in sorted(g['nm_ids'])])],existing_reports=True,economics={str(n):models['rows'][str(n)]for n in g['nm_ids']},evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))))
   io.put('china_agent:new_ad_tests:tracking:v1',tracking)
  # Final whole-package read, after every launch; never silently accept only isolated steps.
  final=listing();byid={c['id']:c for c in final}
  for g,s in zip(a['groups'],e['groups']):check(byid[s['campaign_id']],g,9,True)
  newids={s['campaign_id']for s in e['groups']}
  assert not any(set(allids)&{n['nm_id']for n in c['nm_settings']}for c in final if c['status']in(9,11)and c['id']not in newids),'External duplicate appeared'
  e.update(status='verified',campaign_ids=sorted(newids),total_funding_cny=2000,verified_at=now(),package_readback=dict(status='verified',campaign_ids=sorted(newids),sku_count=73));save()
 except Exception as ex:
  e['status']='uncertain'if any(s.get('status')in('submitting','accepted','uncertain')for g in e['groups']for s in g['steps'].values())else'blocked';e['reason']=str(ex)[:350]or type(ex).__name__;save();raise
 print(json.dumps(dict(status=e['status'],campaign_count=len(e['campaign_ids']),sku_count=73,wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()

