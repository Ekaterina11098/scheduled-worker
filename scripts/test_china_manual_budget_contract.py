import copy,sys,types,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from china_loss_control import digest
from china_manual_budget_contract import contract,validate_funding
class IO:
 def __init__(self):self.rows={}
 def get(self,k):return copy.deepcopy(self.rows.get(k))
def fixture():
 io=IO();i=dict(kind='topup_campaign',campaign_id=123,amount_cny=100,manual_budget_continuation=True,manual_budget_contract='contract',requires_preparation_key='prep',budget_evidence=dict(modeled_after_ads_cny=20,risk_disclosed_before_confirmation=True,period_to='2026-11-15',expected_bids={'10':{'search':28}},member_inputs={'10':dict(article='a',price=200,cost=100,fx=10)},attributed_orders=2))
 io.rows={'prep':dict(status='verified'),'contract':dict(status='ready_for_human_confirmation',grants_action_permission=False,action_sha256=digest([i]),maximum_funding_cny=100,expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())}
 return io,i,dict(status=9,currency='CNY',nm_settings=[dict(nm_id=10,bids_kopecks={'search':28})])
class Manual(unittest.TestCase):
 def test_frozen_scope_and_preparation(self):
  io,i,b=fixture();contract(io,i)
  for field,val in [('amount_cny',200),('campaign_id',124)]:
   bad=copy.deepcopy(i);bad[field]=val
   with self.assertRaises(ValueError):contract(io,bad)
  io.rows['prep']['status']='pending'
  with self.assertRaises(ValueError):contract(io,i)
 def test_current_economics_and_availability(self):
  io,i,b=fixture();s=dict(coverage_complete=True,rows=[dict(article='a',price=10000,stock=2,reserve=0)])
  morning=types.SimpleNamespace(current_prices=lambda *a:dict(rows=[dict(nm_id=10,article='a',seller_price=200)]),published_stock=lambda *a:dict(missing_nm_ids=[],amounts={'10':2}))
  stock=types.SimpleNamespace(read_stock=lambda *a:copy.deepcopy(s))
  with patch.dict(sys.modules,china_morning_readiness=morning,china_moysklad_read=stock):
   self.assertEqual(validate_funding(io,i,b)['current_cost_delta_cny'],0)
   s['rows'][0]['price']=30000
   with self.assertRaises(ValueError):validate_funding(io,i,b)
   s['rows'][0].update(price=10000,stock=0)
   with self.assertRaises(ValueError):validate_funding(io,i,b)
if __name__=='__main__':unittest.main()
