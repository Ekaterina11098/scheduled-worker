import copy,unittest
from china_budget_ready_model import assess_campaign
from china_budget_reserve import apply

class BudgetReview(unittest.TestCase):
 def fixture(self):
  at='2026-11-15T00:00:00+00:00';days=['2026-11-12','2026-11-13','2026-11-14']
  state=dict(id=1,status=9,nm_settings=[dict(nm_id=10)],timestamps=dict(started='2026-11-12T10:00:00+00:00'))
  raw=dict(days=[dict(date=d,sum=10,orders=1,clicks=40,sum_price=100,apps=[dict(nms=[dict(nmId=10,orders=1)])])for d in days])
  e=dict(sample_size=5,buyout=.8,buyout_fallback=False,expected_margin_before_ads_cny=80,own_cogs_rub=100,seller_price_cny=200,fx_rub_per_cny=12,logistics_cny=10,commission_pct=20,observed_at=at,price_observed_at=at,stock_observed_at=at,published_stock_observed_at=at)
  return state,raw,dict(rows={'10':e}),days,at
 def assess(self,s,r,e,d,a,changes=[]):return assess_campaign(s,r,e,{},changes,d,a)
 def test_foreign_order_does_not_hide_no_direct_sales(self):
  s,r,e,d,a=self.fixture()
  for day in r['days']:day['apps'][0]['nms'][0]['nmId']=99
  x=self.assess(s,r,e,d,a);self.assertEqual(x['status'],'review');self.assertFalse(x['ready']);self.assertEqual(x['associated_attributed_orders'],2)
 def test_no_free_associated_incremental_profit(self):
  s,r,e,d,a=self.fixture()
  for day in r['days']:
   day['orders']=2;day['apps'][0]['nms'].append(dict(nmId=99,orders=1))
  e['rows']['99']=dict(e['rows']['10'],expected_margin_before_ads_cny=100000)
  x=self.assess(s,r,e,d,a);self.assertLess(x['modeled_contribution_cny'],1000);self.assertEqual(x['associated_downside_reserve_cny'],0)
  e['rows']['99']['expected_margin_before_ads_cny']=-20
  self.assertGreater(self.assess(s,r,e,d,a)['associated_downside_reserve_cny'],0)
 def test_no_waiting_after_membership_change_with_completed_history(self):
  s,r,e,d,a=self.fixture()
  x=self.assess(s,r,e,d,a,[dict(cid=1,nm=11,kind='excluded',at='2026-11-14T10:00:00+00:00')])
  self.assertEqual(x['evaluation_status'],'waiting');self.assertTrue(x['not_three_full_test_days']);self.assertEqual(x['days'],d)
 def test_planned_only_when_no_own_sample(self):
  s,r,e,d,a=self.fixture();e['rows']['10'].update(sample_size=0,buyout_fallback=True,planned_buyout_source='approved_policy')
  self.assertEqual(self.assess(s,r,e,d,a)['status'],'positive')
  e['rows']['10'].update(sample_size=5)
  self.assertEqual(self.assess(s,r,e,d,a)['status'],'unknown')
 def test_actual_zero_is_not_replaced(self):
  s,r,e,d,a=self.fixture();e['rows']['10'].update(buyout=0,expected_margin_before_ads_cny=-10)
  self.assertEqual(self.assess(s,r,e,d,a)['status'],'review')
 def bundle(self,status=9):
  s,r,e,d,a=self.fixture()
  c=dict(id=1,status=status,never_started=False,balance=5,budget_days=d,budget_started_at=s['timestamps']['started'],budget_period=dict(spend=30,orders=3,amount=300),budget_members=[dict(nm=10)],campaign_budget_economics=dict(status='positive',ready=True,observed_at=a,period_to=d[-1],reason='preliminary',stress_after_ads_cny=20))
  return dict(campaigns=[c],budget_days=d,budget_observed_at=a,budget_balance_observed_at_iso=a)
 def test_partial_launch_reference_preserved_and_ready(self):
  b=self.bundle();c=apply(b)['campaigns'][0]
  self.assertEqual(c['budget_reference_need'],30);self.assertTrue(c['not_three_full_test_days']);self.assertEqual(c['budget_action']['amount_cny'],100)
 def test_paused_negative_is_final_no_fund_not_unfinished(self):
  b=self.bundle(11);b['campaigns'][0]['campaign_budget_economics'].update(status='review',ready=False,reason='Не пополнять')
  c=apply(b)['campaigns'][0];self.assertEqual(c['budget_audit_state'],'reviewed_no_fund');self.assertFalse(c['budget_review_required']);self.assertIsNone(c['budget_action'])
 def test_paused_positive_cannot_restart_without_confirmation(self):
  c=apply(self.bundle(11))['campaigns'][0];self.assertIsNone(c['budget_action']);self.assertTrue(c['budget_review_required'])
 def test_completed_no_fund_is_visible_without_action(self):
  from china_advertising_v2_png import budget_column
  b=self.bundle(11);b['campaigns'][0]['campaign_budget_economics'].update(status='review',ready=False,reason='Модель не покрывает расход')
  c=apply(b)['campaigns'][0]
  self.assertIn('Не пополнять и не возобновлять',budget_column(c));self.assertIsNone(c['budget_action'])

if __name__=='__main__':unittest.main()

