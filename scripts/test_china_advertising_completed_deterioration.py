import unittest
from test_china_advertising_economic_review import fixture
from china_advertising_economic_review import apply

class CompletedDeterioration(unittest.TestCase):
 def evidence(self,spend,orders,amount,clicks,bid,last_spend,last_orders,last_amount,last_clicks):
  b,s,m=fixture(spend=spend,orders=orders,amount=amount,clicks=clicks,bid=bid)
  b.update(day='2026-11-16',days=['2026-11-13','2026-11-14','2026-11-15'])
  c=s['batches']['0']['campaigns']['adverts'][0];c.update(status=9);c['settings']['payment_type']='cpc'
  # Rebuild the complete period from dated rows, including the two earlier days.
  daily=[]
  for day in b['days'][:-1]:
   daily.append(dict(date=day+'T00:00:00Z',apps=[dict(nms=[dict(nmId=10,sum=(spend-last_spend)/2,orders=(orders-last_orders)/2,sum_price=(amount-last_amount)/2,clicks=(clicks-last_clicks)/2,views=2000)])]))
  daily.append(dict(date='2026-11-15T00:00:00Z',apps=[dict(nms=[dict(nmId=10,sum=last_spend,orders=last_orders,sum_price=last_amount,clicks=last_clicks,views=2000)])]))
  s['batches']['0']['stats']=[dict(advertId=1,days=daily)]
  s['economics']['rows']['10'].update(sample_size=100,buyout_fallback=False,commission_policy_fallback=False)
  return b,s,m
 def test_good_three_day_own_model_does_not_hide_last_completed_day_without_orders(self):
  b,s,m=self.evidence(171.08,6,1309,611,28,90.44,0,0,323);s['economics']['rows']['10']['expected_margin_before_ads_cny']=33.12
  r=apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertEqual(r['action']['kind'],'ad_exclude_sku');self.assertTrue(r['completed_cost_guard']['latest_zero_loss'])
 def test_completed_deterioration_can_reduce_a_positive_own_model_above_minimum(self):
  b,s,m=self.evidence(143.63,6,1710,417,35,78.04,2,570,227);s['economics']['rows']['10']['expected_margin_before_ads_cny']=39.8
  r=apply(b,s,m)['campaigns'][0]['focus'][0];self.assertEqual(r['action']['target_minor'],28)
 def test_repeated_zero_order_traffic_is_not_allowed_to_wait_for_a_high_unit_margin_forever(self):
  b,s,m=self.evidence(42.84,0,0,153,28,37.52,0,0,134);s['economics']['rows']['10'].update(expected_margin_before_ads_cny=66.94,seller_price_cny=434.5)
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'][0]['action']['kind'],'ad_exclude_sku')
 def test_owner_protected_product_cannot_receive_the_same_cut(self):
  b,s,m=self.evidence(171.08,6,1309,611,28,90.44,0,0,323)
  b['campaigns'][0]['focus'][0]['nm']=1473245494;s['batches']['0']['campaigns']['adverts'][0]['nm_settings'][0]['nm_id']=1473245494
  self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])
if __name__=='__main__':unittest.main()
