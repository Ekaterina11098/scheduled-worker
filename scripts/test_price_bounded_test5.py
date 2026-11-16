import unittest
from china_price_economic_target import choose_target
class BoundedPriceTest(unittest.TestCase):
 def target(self,allowed,cost=100):
  old=dict(current_cny=80,base_cny=160,discount=50);current=dict(current_cny=100,base_cny=200,discount=50)
  before=dict(expected_profit_per_day=100,orders_per_day=1,views=100,days=1)
  after=dict(advertising_per_day=20,orders_per_day=0,views=100,days=1)
  return choose_target(old,current,before,after,buyout_probability=.5,retention=.72,cost=cost,dispatch=10,fx=12,allow_bounded_first5_test=allowed)
 def test_no_implied_permission(self):
  self.assertEqual(self.target(False)['status'],'first_decrease_cap_no_supported_intermediate_demand')
 def test_explicit_bounded_test_never_claims_old_profit_recovery(self):
  r=self.target(True)
  self.assertEqual(r['status'],'recommended_test');self.assertEqual(r['price_cny'],95)
  self.assertGreater(r['unit_contribution_rub'],0)
  self.assertIsNone(r['predicted_profit_per_day']);self.assertIsNone(r['predicted_orders_per_day'])
  self.assertEqual(r['demand_recovery'],'unidentified_not_claimed')
  self.assertFalse(r['execution_authorized'])
 def test_negative_unit_economics_still_blocks(self):
  self.assertEqual(self.target(True,cost=10000)['status'],'no_positive_unit_economics')
if __name__=='__main__':unittest.main()

