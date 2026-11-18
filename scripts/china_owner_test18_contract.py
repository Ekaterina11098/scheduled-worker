"""One exact owner-requested GUA funding proposal, not a general relaxation."""
from datetime import datetime,timezone
from decimal import Decimal
KEY='china_agent:owner_report18_fix:v1:41779660:funding_contract'
IDS={2128836688,2129199357,2129309884,2129309885}
def check_record(io,item,before):
 from china_loss_control import digest
 r=io.get(KEY)or{}
 if (item.get('manual_budget_contract')!=KEY or item.get('campaign_id')!=41779660 or not item.get('owner_requested_test_20261118')
     or item.get('kind')!='topup_campaign' or before.get('id')!=41779660 or before.get('status')!=9 or before.get('currency')!='CNY'
     or r.get('status')!='ready_for_human_confirmation' or r.get('grants_action_permission')is not False
     or r.get('owner_id')!=5122667182 or not r.get('source_owner_request') or r.get('risk_disclosed_before_confirmation')is not True
     or r.get('action_sha256')!=digest([item]) or r.get('maximum_funding_cny')!=item.get('amount_cny')
     or not 100<=item['amount_cny']<=300 or datetime.now(timezone.utc)>=datetime.fromisoformat(r.get('expires_at','2000-01-01T00:00:00+00:00'))):
  raise ValueError('Exact owner test funding contract missing, expired or changed')
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 if set(map(int,actual))!=IDS or actual!=item['budget_evidence']['expected_bids']:raise ValueError('Selected GUA test composition/bids changed')
 return r
def validate(io,item,before):
 check_record(io,item,before)
 from china_morning_readiness import current_prices
 from china_moysklad_read import read_stock
 route=(io.get('china_agent:campaign_economics_routes:v1')or{}).get('campaigns',{}).get('41779660',{})
 e=item['budget_evidence']
 if route.get('warehouse_role')!='guangzhou' or route.get('warehouse_id')!=e['warehouse_id'] or route.get('published_warehouse_id')!=e['published_warehouse_id'] or set(route.get('nm_ids',[]))!=IDS:raise ValueError('GUA route identity changed')
 prices=current_prices(io,sorted(IDS));stock=read_stock([p['article']for p in prices['rows']],warehouse_role='guangzhou')
 if not stock.get('coverage_complete') or stock.get('warehouse_id')!=route['warehouse_id']:raise ValueError('GUA stock/COGS incomplete')
 import requests
 mapping=e['size_to_nm'];rr=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/'+str(route['published_warehouse_id']),headers={'Authorization':io.token},json=dict(chrtIds=list(map(int,mapping))),timeout=50)
 rr.raise_for_status();raw=rr.json()
 pub={nm:0 for nm in IDS};seen=set()
 for s in raw['stocks']:
  nm=mapping.get(str(s.get('chrtId',s.get('chrtID'))))
  if nm not in IDS:raise ValueError('Published GUA stock outside scope')
  seen.add(nm);pub[nm]+=s['amount']
 if seen!=IDS:raise ValueError('Published GUA stock coverage incomplete')
 rows={s['article'].casefold():s for s in stock['rows']};available=[];unavailable=[]
 for p in prices['rows']:
  old=e['member_inputs'][str(p['nm_id'])];st=rows[p['article'].casefold()]
  if Decimal(str(p['seller_price']))!=Decimal(str(old['price'])) or not st.get('price') or st['price']<=0:raise ValueError('GUA price or COGS changed/missing')
  fx=old['fx'];q=old['buyout'];margin=q*(p['seller_price']*.72-st['price']/100/fx)-old['logistics_cny']
  if st['stock']-st['reserve']>0 and pub[p['nm_id']]>0:
   if margin<=0:raise ValueError('GUA own preliminary unit economics no longer positive')
   available.append(p['nm_id'])
  else:unavailable.append(p['nm_id'])
 if not available:raise ValueError('No available GUA test product')
 return dict(warehouse_role='guangzhou',available_nm_ids=available,unavailable_nm_ids=unavailable,positive_unit_model=True,whole_campaign_profit_proven=False,owner_requested_bounded_continuation=True)

