"""Exact report-scoped manual experiments; no standing funding authority."""
import copy
from datetime import datetime,timezone
def contract(io,item):
 from china_loss_control import digest
 key=item.get('manual_budget_contract')or item.get('continuation_contract')
 record=io.get(key or'')or{};now=datetime.now(timezone.utc)
 if (record.get('status')!='ready_for_human_confirmation'or record.get('grants_action_permission')is not False
     or record.get('action_sha256')!=digest([item])or record.get('maximum_funding_cny')!=item.get('amount_cny')
     or now>=datetime.fromisoformat(record.get('expires_at','2000-01-01T00:00:00+00:00'))):raise ValueError('Frozen manual budget proposal changed or expired')
 evidence=item.get('budget_evidence')or item.get('recovery_evidence')or{}
 from zoneinfo import ZoneInfo
 if (evidence.get('modeled_after_ads_cny',0)<=0 or evidence.get('risk_disclosed_before_confirmation')is not True
     or evidence.get('period_to','9999')>=str(now.astimezone(ZoneInfo('Europe/Moscow')).date())):raise ValueError('Completed, disclosed manual economic evidence missing')
 dep=item.get('requires_preparation_key')
 if dep and (io.get(dep)or{}).get('status')!='verified':raise ValueError('Сначала завершите подтверждённые изменения рекламного PNG')
 return record

def validate_funding(io,item,before):
 if item.get('owner_requested_test_20261118'):
  from china_owner_test18_contract import validate
  return validate(io,item,before)
 contract(io,item)
 from china_morning_readiness import current_prices,published_stock
 from china_moysklad_read import read_stock
 e=copy.deepcopy(item['budget_evidence'])
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 if before['status']!=9 or before['currency']!='CNY':raise ValueError('Active CNY campaign required')
 if actual!=e['expected_bids']:
  from china_confirmed_funding_context import reconcile
  e=reconcile(io,e,before)
 old_inputs=copy.deepcopy(e['member_inputs'])
 for nm,model in e.get('conditional_purchase_models',{}).items():
  old_inputs.setdefault(nm,dict(article=model['article'],price=model['seller_price_cny'],cost=model['own_cogs_rub'],fx=model['fx_rub_per_cny']))
 ids=sorted(map(int,old_inputs));prices=current_prices(io,ids)
 if {r['nm_id']for r in prices['rows']}!=set(ids):raise ValueError('Exact manual price coverage missing')
 current=copy.deepcopy(prices);current['rows']=[r for r in current['rows']if str(r['nm_id'])in actual]
 pub=published_stock(io,current,list(map(int,actual)))
 articles=[r['article']for r in prices['rows']];parts=[read_stock(articles[start:start+20])for start in range(0,len(articles),20)]
 if not all(s['coverage_complete']for s in parts)or pub['missing_nm_ids']:raise ValueError('Fresh manual budget availability incomplete')
 stocks={r['article'].casefold():r for part in parts for r in part['rows']};delta=0;unavailable_reserve=0;unavailable=[]
 for row in prices['rows']:
  nm=str(row['nm_id']);old=old_inputs[nm];stock=stocks[row['article'].casefold()]
  if row['seller_price']!=old['price']or not stock.get('price')or stock['price']<=0:raise ValueError('Manual budget price/COGS changed: '+row['article'])
  missing_stock=nm in actual and (stock['stock']-stock['reserve']<=0 or pub['amounts'][nm]<=0)
  fx=float(old.get('fx')or e.get('fx_rub_per_cny')or 0)
  if fx<=0:raise ValueError('Manual budget FX missing')
  # All attributions carry all positive cost increases at100%buyout: no profit credit from decreases/new orders.
  delta+=max(0,stock['price']/100-old['cost'])/fx
  if missing_stock:
   count=e.get('attributed_orders_by_nm',{}).get(nm,0);q=old.get('buyout')
   if type(count)not in(int,float)or type(q)not in(int,float)or not 0<=q<=1:raise ValueError('Unavailable SKU contribution unknown')
   unavailable_reserve+=count*q*max(0,old['price']-old['cost']/fx)
   unavailable.append(nm)
 bound=e.get('attributed_orders',e.get('metrics',{}).get('orders'))
 if type(bound)not in(int,float)or bound<0 or len(unavailable)==len(actual)or e['modeled_after_ads_cny']-bound*delta-unavailable_reserve<=0:raise ValueError('Current COGS no longer supports disclosed manual scenario')
 return dict(current_cost_delta_cny=bound*delta,unavailable_nm_ids=unavailable,unavailable_contribution_upper_bound_cny=unavailable_reserve,remaining_modeled_after_ads_cny=e['modeled_after_ads_cny']-bound*delta-unavailable_reserve,associated_profit_not_proven=True)

