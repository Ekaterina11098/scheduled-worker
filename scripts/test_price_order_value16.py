import unittest
from china_price_economic_target import choose_target
class PriceGrowthObjective(unittest.TestCase):
 def call(self,orders=1,cost=5):
  return choose_target(dict(current_cny=95,base_cny=190,discount=50),dict(current_cny=100,base_cny=200,discount=50),dict(expected_profit_per_day=10000,orders_per_day=3,views=100,days=1),dict(orders_per_day=orders,advertising_per_day=10,views=100,days=1),buyout_probability=.5,retention=.7,cost=cost,dispatch=1,fx=1,objective='order_value_positive_economics')
 def test_prior_profit_is_diagnostic(self):
  r=self.call();self.assertEqual(r['status'],'recommended');self.assertLess(r['expected_profit_advantage_per_day'],0);self.assertGreater(r['predicted_profit_per_day'],0);self.assertGreater(r['order_value_advantage_per_day'],0)
 def test_cap_and_discount(self):
  r=self.call();self.assertGreaterEqual(r['price_cny'],95);self.assertEqual(r['discount'],50)
 def test_no_negative_economics(self):self.assertNotEqual(self.call(cost=10000)['status'],'recommended')
 def test_hold_orders(self):self.assertEqual(self.call(orders=3)['status'],'orders_and_amount_not_declining')
if __name__=='__main__':unittest.main()
