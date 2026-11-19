import copy,sys,types,unittest
from datetime import datetime
from unittest.mock import patch
from china_advertising_full_growth import proposed_actions
from china_advertising_decision_contract import comparable_action
def fixture(balance):
 c=dict(id=10,status=9,currency='CNY',bid_type='manual',settings=dict(payment_type='cpc',placements=dict(search=False,recommendations=True)),timestamps={'started':'2026-11-01T00:00:00Z'},nm_settings=[dict(nm_id=1,bids_kopecks=dict(search=0,recommendations=28))])
 raw=dict(advertId=10,days=[dict(date='2026-11-'+str(d),sum=5,apps=[dict(nms=[dict(nmId=1,sum=5,sum_price=500,orders=5,clicks=50,views=1000)])])for d in(16,17,18)])
 e=dict(stock_free=100,published_stock=100,sample_size=20,buyout_fallback=False,commission_policy_fallback=False,fx_rub_per_cny=12,logistics_cny=10,expected_margin_before_ads_cny=80,buyout=.5,seller_price_cny=200,commission_pct=20,tax_pct=5,own_cogs_rub=600)
 v=dict(own={'rows':[dict(nm_id=1,commentsvaluation=5)]},prices={'rows':[dict(nm_id=1,article='one')]},economics={'rows':{'1':e}},budgets={'adverts':[dict(advertId=10,total=balance)]},campaigns=[c],excluded_nm_ids=[],config=dict(cpcStep=1,cpcMaxBid=1290),minimums={'10':{'bids':[dict(nm_id=1,bids=[dict(type='recommendation',currency='CNY',value=28)])]}},observed_at='2026-11-19T07:00:00Z')
 e['price_observed_at']='2026-11-19T07:00:00Z';v['own']['observed_at']='2026-11-19T07:00:00Z'
 return dict(period_to='2026-11-18',executions=[],batches={'x':{'stats':[raw]}},full_growth_inputs=v)
class Advisory(unittest.TestCase):
 def evaluate(self,s,events=None):
  module=types.SimpleNamespace(history=lambda x:events or[],event_time=lambda x:datetime.fromisoformat(x.replace('Z','+00:00')))
  with patch.dict(sys.modules,{'china_advertising_v2':module}):return proposed_actions(s)
 def test_balance_cannot_remove_eligible_raise_or_create_deposit(self):
  decisions=[]
  for balance in(0,1,10000):
   actions,blocked=self.evaluate(fixture(balance));self.assertEqual(1,len(actions));self.assertEqual([],blocked)
   self.assertFalse(actions[0]['growth_evidence']['budget_forecast']['grants_funding_permission']);decisions.append((actions[0]['kind'],actions[0]['target_minor']))
  self.assertEqual([('ad_set_bid',30)]*3,decisions)
 def test_stock_economics_and_same_day_guards_survive(self):
  for field,value in [('stock_free',0),('expected_margin_before_ads_cny',-1),('published_stock',0)]:
   s=fixture(0);s['full_growth_inputs']['economics']['rows']['1'][field]=value;self.assertEqual([],self.evaluate(s)[0])
  self.assertEqual([],self.evaluate(fixture(0),[dict(nm=1,kind='bid',at='2026-11-19T06:00:00Z')])[0])
 def test_advisory_cash_drift_is_not_a_different_bid(self):
  a=self.evaluate(fixture(0))[0][0];b=copy.deepcopy(a);b['growth_evidence']['budget_forecast']['balance_cny']=5
  self.assertEqual(comparable_action(a),comparable_action(b));b['target_minor']+=1;self.assertNotEqual(comparable_action(a),comparable_action(b))
if __name__=='__main__':unittest.main()

