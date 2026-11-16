import unittest
from test_china_advertising_economic_review import fixture
from china_advertising_economic_review import apply

class FloorCost(unittest.TestCase):
 def test_completed_zero_orders_beyond_one_own_margin_is_reviewed_at_floor_too(self):
  b,s,m=fixture(spend=26.04,clicks=93,bid=28)
  s['economics']['rows']['10'].update(expected_margin_before_ads_cny=23.598461247988787,sample_size=7,buyout_fallback=False,commission_policy_fallback=False)
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'][0]['action']['kind'],'ad_exclude_sku')
 def test_negative_reliable_unit_model_does_not_need_another_five_percent_of_price(self):
  b,s,m=fixture(spend=4.48,clicks=16,bid=28)
  s['economics']['rows']['10'].update(expected_margin_before_ads_cny=-3.24,seller_price_cny=421.92,sample_size=24,sample_reliable=True,buyout_fallback=False,commission_policy_fallback=False)
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'][0]['action']['kind'],'ad_exclude_sku')
 def test_same_negative_model_on_change_day_cannot_cut(self):
  b,s,m=fixture(spend=4.48,clicks=16,bid=28);b['campaigns'][0]['focus'][0]['pending_first_day']=True
  s['economics']['rows']['10'].update(expected_margin_before_ads_cny=-3.24,sample_size=24,sample_reliable=True)
  self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])
 def test_low_exposure_with_positive_unit_margin_is_not_cut(self):
  b,s,m=fixture(spend=4.32,clicks=16,bid=28)
  s['economics']['rows']['10'].update(expected_margin_before_ads_cny=11.53,sample_size=15)
  self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])
if __name__=='__main__':unittest.main()
