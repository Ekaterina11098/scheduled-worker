"""Exact human-confirmed, bounded selected-composition test. No automatic funding."""
import copy
from datetime import datetime,timezone
CONTRACT='china_agent:selected_campaign_test:v1:'
PREPARATION='china_agent:selected_campaign_preparation:v1:'

def validate_preparation_item(io,item,before):
 from china_loss_control import digest
 contract=io.get(item.get('preparation_ref',''))or{}
 assert contract.get('status')in('ready_for_human_confirmation','verified')and contract.get('grants_action_permission')is False
 assert contract.get('action_hashes',{}).get(item['id'])==digest([item]),'Preparation item changed'
 assert datetime.now(timezone.utc)<datetime.fromisoformat(contract['expires_at']),'Preparation expired'
 assert before['id']==contract['campaign_id']==item['campaign_id']and before['status']==11
 expected=contract['expected_bids'];ids={n['nm_id']for n in before['nm_settings']}
 assert set(contract['keep_nm_ids'])<=ids<=set(map(int,expected)),'Preparation composition changed'
 for n in before['nm_settings']:
  bids=n['bids_kopecks'];old=expected[str(n['nm_id'])]
  assert bids==old or n['nm_id']in contract['keep_nm_ids']and bids==dict(old,**{contract['placement']:contract['target_minor']}),'Preparation bid changed'
 return True

def publish_preparation(io,items,states,execution_key):
 for ref in {i.get('preparation_ref')for i in items if i.get('preparation_ref')}:
  c=io.get(ref);byid={s['id']:s for s in states}
  if not c or not all(byid.get(k,{}).get('status')=='verified'for k in c['action_hashes']):continue
  matches=[s['after']for k,s in byid.items()if k in c['action_hashes']and s.get('after')]
  after=next((a for a in reversed(matches)if a['status']==11 and sorted(n['nm_id']for n in a['nm_settings'])==sorted(c['keep_nm_ids'])and all(n['bids_kopecks'][c['placement']]==c['target_minor']for n in a['nm_settings'])),None)
  if not after:continue
  routes=io.get('china_agent:campaign_economics_routes:v1');routes['campaigns'][str(c['campaign_id'])]['nm_ids']=sorted(c['keep_nm_ids']);io.put('china_agent:campaign_economics_routes:v1',routes)
  c.update(status='verified',execution_key=execution_key,after=after,verified_at=datetime.now(timezone.utc).isoformat());io.put(ref,c)

def validate_contract(io,item,before,now=None):
 from china_loss_control import digest
 now=now or datetime.now(timezone.utc)
 contract=io.get(item.get('selected_test_contract',''))or{}
 assert item.get('selected_test')is True and item['kind']=='recover_campaign','Selected test scope missing'
 assert item['selected_test_contract']==CONTRACT+str(item['campaign_id'])+':'+item['id'],'Wrong test contract'
 assert contract.get('status')=='ready_for_human_confirmation' and contract.get('grants_action_permission')is False,'Not a prepared proposal'
 assert contract.get('action_sha256')==digest([item]),'Frozen test action changed'
 assert now<datetime.fromisoformat(contract['expires_at']),'Test proposal expired'
 assert before['id']==item['campaign_id'] and before['status']==11 and before['currency']=='CNY','Paused CNY campaign required'
 assert before['bid_type']=='manual' and before['settings']['payment_type']=='cpc'
 assert not({1473245494,1473245510}&set(item['nm_ids']))and before['id']!=40811856,'Protected campaign/product'
 preparation=io.get(item.get('requires_preparation_key',''))or{}
 assert preparation.get('status')=='verified','Сначала подтвердите состав и ставки в рекламном PNG'
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 e=item['recovery_evidence'];keep=set(item['nm_ids']);remove=set(item['remove_nm_ids'])
 assert actual==e['expected_bids'] and keep and not remove and keep==set(map(int,actual)),'Composition/bids changed'
 assert before==preparation['after'],'Prepared campaign changed'
 assert e['preliminary']is True and e['modeled_after_ads_cny']>0 and e['risk_disclosed_before_confirmation']is True
 assert item['review_scope_text'] and e['stress_after_ads_cny']<0,'Explicit risk disclosure missing'
 assert type(item['amount_cny'])is int and 0<item['amount_cny']<=contract['maximum_funding_cny']
 assert item['amount_cny']==contract['maximum_funding_cny'] and item['target_minor']>0
 assert all(0<item['target_minor']<=actual[str(n)][item['placement']]for n in keep),'No increases in selected test'
 assert 0<=(now-datetime.fromisoformat(e['observed_at'].replace('Z','+00:00'))).total_seconds()<=24*3600,'Test economics expired'
 from zoneinfo import ZoneInfo
 assert e['period_to']<now.astimezone(ZoneInfo('Europe/Moscow')).date().isoformat(),'Completed days only'
 return contract

def current_economics(io,item,req):
 from china_morning_readiness import current_prices
 from china_moysklad_read import read_stock
 from china_campaign_routes import guangzhou_models
 cid=item['campaign_id'];e=item['recovery_evidence'];ids=set(item['nm_ids'])
 route=copy.deepcopy((io.get('china_agent:campaign_economics_routes:v1')or{})['campaigns'][str(cid)])
 assert route['warehouse_role']=='guangzhou' and set(route['nm_ids'])==set(map(int,e['expected_bids'])),'Route scope changed'
 route['nm_ids']=sorted(ids)
 prices=current_prices(io,sorted(ids));assert {r['nm_id']for r in prices['rows']}==ids
 stock=read_stock([r['article']for r in prices['rows']],warehouse_role='guangzhou')
 cards=io.get('china_agent:campaign_route_cards:v1:'+str(cid));assert cards
 cards=dict(cards,rows=[r for r in cards['rows']if r['nmID']in ids])
 assert {r['nmID']for r in cards['rows']}==ids
 mapping={str(z['chrtID']):r['nmID']for r in cards['rows']for z in r['sizes']}
 import requests
 rr=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/'+str(route['published_warehouse_id']),json={'chrtIds':list(map(int,mapping))},headers={'Authorization':io.token},timeout=50)
 rr.raise_for_status();published=dict(warehouse_id=route['published_warehouse_id'],observed_at=datetime.now(timezone.utc).isoformat(),size_to_nm=mapping,raw=rr.json())
 saved=io.get(e['inputs_key']);assert saved
 v=copy.deepcopy(saved)
 v['prices']=dict(prices,rows=[dict(nm_id=r['nm_id'],article=r['article'],seller_price=r['seller_price'])for r in prices['rows']])
 # model_rows expects the same live-price shape as full-growth collection.
 v['prices']['rows']=[dict(r,seller_price_cny=r['seller_price'])for r in v['prices']['rows']]
 model=guangzhou_models(v,route,dict(stock=stock,cards=cards,published=published),io.get('china_agent:new_ad_economics_policy:v1')or{})
 net=0
 for nm,m in model['rows'].items():
  old=e['member_inputs'][nm]
  assert m['seller_price_cny']==old['price']and m['own_cogs_rub']<=old['cost']+.01,'Price or COGS changed'
  assert m['stock_free']>0 and m['published_stock']>0 and m['buyout']==old['buyout'],'Availability/buyout changed'
  assert m['logistics_cny']<=old['logistics_cny']+.001 and m['expected_margin_before_ads_cny']>0,'Tariff/economics changed'
  net+=m['expected_margin_before_ads_cny']*e['traffic'][nm]['orders']-e['traffic'][nm]['clicks']*item['target_minor']/100
 assert net>0,'Current base economics no longer positive'
 return dict(observed_at=datetime.now(timezone.utc).isoformat(),modeled_after_ads_cny=net,models=model,route=route)

def execute(io,item,state,save,req,campaign,budget):
 if state.get('steps'):raise ValueError('Existing selected test journal; no automatic replay')
 before=campaign(item['campaign_id']);validate_contract(io,item,before)
 assert not(io.get('china_agent:budget_owner_policy:v1')or{}).get('do_not_fund',{}).get(str(item['campaign_id'])),'Current owner funding hold'
 ids=sorted(item['nm_ids']);cid=item['campaign_id'];zone=item['placement'];target=item['target_minor']
 quote=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=ids,payment_type='cpc',placement_types=['search'if zone=='search'else'recommendation']))
 minima={r['nm_id']:next((b['value']for b in r['bids']if b['currency']=='CNY'and b['type']==('search'if zone=='search'else'recommendation')),None)for r in quote['bids']}
 assert set(minima)==set(ids)and all(type(x)is int and 0<x<=target for x in minima.values()),'Current minimum changed'
 evidence=current_economics(io,item,req)
 def cash():
  rows=req('/api/advert/v2/budget','POST',dict(advertIds=[cid]))['adverts'];assert len(rows)==1 and rows[0]['advertId']==cid
  r=rows[0];assert r.get('currency')=='CNY'or r.get('currency')in('',None)and r['total']==0
  return r['total']
 initial=cash();assert initial==item['balance_before'],'Budget changed; do not repeat funding'
 cfg=req('/api/advert/v1/config');wallet=req('/adv/v1/balance');amount=item['amount_cny']
 assert cfg['currency']==wallet['currency']=='CNY'and cfg['minTopUp']<=amount*100
 source=0 if wallet.get('balance',0)>=amount else 1 if wallet.get('net',0)>=amount else None
 assert source is not None,'Insufficient CNY wallet'
 state.update(before=before,before_budget=initial,steps=[],current_economics=evidence);save();expected=copy.deepcopy(before)
 def same(status):
  got=campaign(cid)
  return got['status']==status and all(got[k]==expected[k]for k in('id','currency','bid_type','settings'))and sorted(got['nm_settings'],key=lambda n:n['nm_id'])==sorted(expected['nm_settings'],key=lambda n:n['nm_id'])
 def step(label,path,method,body,verify):
  from china_daily_report_validity import require
  require(io,io.daily_report_plan)
  row=dict(id=label,status='submitting',request=dict(path=path,method=method,body=body));state['steps'].append(row);state['status']='submitting';save()
  try:
   row['response']=req(path,method,body);row['status']='accepted';state['wb_writes']=state.get('wb_writes',0)+1;save()
   for _ in range(20):
    if verify():row.update(status='verified',verified_at=datetime.now(timezone.utc).isoformat());state['status']='preflight';save();return
    __import__('time').sleep(3)
   raise ValueError('Selected test readback mismatch')
  except Exception:row['status']='uncertain';state['status']='uncertain';save();raise
 assert same(11)and cash()==initial,'Campaign changed during preflight'
 state['steps']=[dict(id='composition',status='verified',read_only=True),dict(id='bids',status='verified',read_only=True)];save()
 assert cash()==initial and same(11),'Budget/state changed before funding'
 step('fund','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=amount,type=source),lambda:same(11)and cash()>=initial+amount)
 assert same(11)and cash()>0,'Selected test prerequisites not verified'
 step('resume','/adv/v0/start?id='+str(cid),'GET',None,lambda:same(9))
 state.update(status='verified',after=campaign(cid),after_budget=cash(),verified_at=datetime.now(timezone.utc).isoformat());save()
 routes=io.get('china_agent:campaign_economics_routes:v1');routes['campaigns'][str(cid)]['nm_ids']=ids
 routes['campaigns'][str(cid)]['verified_selected_test']=dict(action_id=item['id'],verified_at=state['verified_at'],previous_nm_ids=sorted(map(int,item['recovery_evidence']['expected_bids'])))
 io.put('china_agent:campaign_economics_routes:v1',routes)
 return state['wb_writes']

