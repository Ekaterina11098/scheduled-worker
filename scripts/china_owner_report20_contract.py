"""Frozen owner-reviewed 20Nov proposals. No standing funding permission."""
import copy
from datetime import datetime,timezone
from decimal import Decimal
ROOT='china_agent:owner_publish_reports:2026-11-20:r1'

def check(io,item,before):
 from china_loss_control import digest
 c=io.get(item.get('owner_report20_contract',''))or{}
 now=datetime.now(timezone.utc)
 if (item.get('owner_report20_contract')!=ROOT+':contract:'+str(item['campaign_id'])
     or item.get('campaign_id')!=c.get('campaign_id')
     or c.get('status')!='ready_for_human_confirmation' or c.get('grants_action_permission')is not False
     or c.get('action_sha256')!=digest([item]) or c.get('maximum_funding_cny')!=item['amount_cny']
     or now>=datetime.fromisoformat(c.get('expires_at','2000-01-01T00:00:00+00:00'))):
  raise ValueError('Exact reviewed20 funding contract changed or expired')
 if c['period_to']>='2026-11-20' or not c.get('risk_disclosed_before_confirmation'):raise ValueError('Reviewed completed-day evidence missing')
 if before['id']!=item['campaign_id'] or before['currency']!='CNY' or before['status']!=item['status_before']:raise ValueError('Campaign status changed')
 if (io.get('china_agent:budget_owner_policy:v1')or{}).get('do_not_fund',{}).get(str(before['id'])):raise ValueError('Owner funding hold')
 e=copy.deepcopy(item['budget_evidence'])
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 if actual!=e['expected_bids']:
  from china_confirmed_funding_context import reconcile
  e=reconcile(io,e,before)
 if actual!=e['approved_target_bids']:raise ValueError('First confirm all displayed companion changes for this campaign')
 return c,e

def validate(io,item,before):
 c,e=check(io,item,before)
 from china_morning_readiness import current_prices,published_stock
 from china_moysklad_read import read_stock
 ids=sorted(map(int,e['approved_target_bids']));prices=current_prices(io,ids)
 if {r['nm_id']for r in prices['rows']}!=set(ids):raise ValueError('Exact reviewed20 price coverage missing')
 pub=published_stock(io,prices,ids);articles=[r['article']for r in prices['rows']]
 parts=[read_stock(articles[i:i+20])for i in range(0,len(articles),20)]
 if pub['missing_nm_ids']or not all(p['coverage_complete']for p in parts):raise ValueError('Reviewed20 stock/COGS coverage incomplete')
 stocks={r['article'].casefold():r for p in parts for r in p['rows']};available=0;delta=Decimal(0)
 for r in prices['rows']:
  nm=str(r['nm_id']);old=e['unit_models'][nm];s=stocks[r['article'].casefold()]
  if Decimal(str(r['seller_price']))!=Decimal(str(old['seller_price_cny'])):raise ValueError('Seller price changed: '+r['article'])
  if s['stock']-s['reserve']<=0 or pub['amounts'][nm]<=0:
   if old.get('stock_free',0)>0 and old.get('published_stock',0)>0:raise ValueError('Availability changed: '+r['article'])
   continue
  if not s.get('price')or s['price']<=0:raise ValueError('Missing current COGS: '+r['article'])
  fx=Decimal(str(old['fx_rub_per_cny']));q=Decimal(str(old['buyout']))
  increase=max(Decimal(0),Decimal(str(s['price']/100))-Decimal(str(old['own_cogs_rub'])))/fx
  if item['kind']=='recover_campaign'and Decimal(str(old['expected_margin_before_ads_cny']))-q*increase<=0:raise ValueError('Unit economics no longer positive: '+r['article'])
  delta+=increase;available+=1
 if not available or item['kind']=='recover_campaign'and available!=len(ids):raise ValueError('No complete available test composition')
 if item['kind']=='topup_campaign'and e['scenario_after_ads_cny']-float(delta)*e['scenario_orders']<=0:raise ValueError('Reviewed provisional continuation scenario no longer positive')
 return {'available_members':available,'cogs_upper_bound_delta_cny':float(delta),'profit_proven':False}

def recover(io,item,state,save,req,campaign,budget):
 if state.get('steps'):raise ValueError('Existing bounded test journal: do not replay')
 cid=item['campaign_id'];before=campaign(cid);c,e=check(io,item,before)
 if not c.get('bounded_new_test')or before['status']!=11 or before['settings']['payment_type']!='cpc':raise ValueError('Wrong bounded test scope')
 state['current_economics']=validate(io,item,before)
 ids=sorted(map(int,e['approved_target_bids']))
 quote=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=ids,payment_type='cpc',placement_types=['search']))
 mins={r['nm_id']:next((b['value']for b in r['bids']if b['type']=='search'and b['currency']=='CNY'),None)for r in quote['bids']}
 if set(mins)!=set(ids)or any(not isinstance(mins[n],int)or not 0<mins[n]<=e['approved_target_bids'][str(n)]['search']for n in ids):raise ValueError('Current minimum changed')
 initial=budget(cid)
 if initial!=item['balance_before']:raise ValueError('Budget changed; do not repeat funding')
 cfg=req('/api/advert/v1/config');wallet=req('/adv/v1/balance');amount=item['amount_cny']
 if cfg['currency']!=wallet['currency']or wallet['currency']!='CNY'or cfg['minTopUp']>amount*100:raise ValueError('Funding currency/minimum changed')
 source=0 if wallet.get('balance',0)>=amount else 1 if wallet.get('net',0)>=amount else None
 if source is None:raise ValueError('Insufficient wallet')
 state.update(before=before,before_budget=initial,steps=[]);save()
 def same(status):
  got=campaign(cid)
  return got['status']==status and all(got[k]==before[k]for k in('id','currency','bid_type','settings'))and sorted(got['nm_settings'],key=lambda n:n['nm_id'])==sorted(before['nm_settings'],key=lambda n:n['nm_id'])
 def step(label,path,method,body,verify):
  from china_daily_report_validity import require
  require(io,io.daily_report_plan)
  row=dict(id=label,status='submitting');state['steps'].append(row);state['status']='submitting';save()
  try:
   row['response']=req(path,method,body);row['status']='accepted';state['wb_writes']=state.get('wb_writes',0)+1;save()
   for _ in range(20):
    if verify():row['status']='verified';state['status']='preflight';save();return
    __import__('time').sleep(3)
   raise ValueError('Bounded test readback mismatch')
  except Exception:row['status']='uncertain';state['status']='uncertain';save();raise
 if not same(11)or budget(cid)!=initial:raise ValueError('State changed before deposit')
 step('fund','/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=amount,type=source),lambda:same(11)and budget(cid)>=initial+amount)
 if not same(11)or budget(cid)<=0:raise ValueError('Funding not verified')
 step('resume','/adv/v0/start?id='+str(cid),'GET',None,lambda:same(9))
 state.update(status='verified',after=campaign(cid),after_budget=budget(cid),verified_at=datetime.now(timezone.utc).isoformat());save()
 return state['wb_writes']

