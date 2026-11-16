import unittest
from datetime import date
from types import SimpleNamespace
from china_price_aggregate_control import membership_override
from china_price_economic_target import choose_target

class PriceMembershipPolicy(unittest.TestCase):
 def test_buyer_anchor_uses_matching_direct_price_not_display_spp(self):
  from china_buyer_price_forecast import build,forecast
  raw=dict(nm_id=1,sa_name='sku',price_final=1004,price_after_spp=1004,price_after_discount=1130,price_spp=17)
  marker=dict(id=1,collected_at='2026-11-16T07:32:54+00:00',period_from='2026-11-15',period_to='2026-11-15')
  cat=dict(cabinet='token_3',observed_at='2026-11-16T07:31:00+00:00',rows=[dict(nmID=1,vendorCode='sku',currencyIsoCode4217='CNY',sizes=[dict(discountedPrice=93.6)])])
  basis=build([raw],marker,cat,date(2026,11,16))
  self.assertIn('1',basis['display_spp_conflicts'])
  self.assertIsNone(basis['rows']['1']['spp_percent'])
  self.assertEqual(forecast(basis,'1','sku',93.6,89.28,date(2026,11,16)),958)
  raw['price_final']=1005
  self.assertNotIn('1',build([raw],marker,cat,date(2026,11,16))['rows'])
 def worker(self,policy):return SimpleNamespace(get=lambda key:policy)
 def test_no_implicit_override(self):
  self.assertFalse(membership_override(self.worker({}),{'status':'membership_changed'}))
 def test_explicit_owner_override_only_changed_membership(self):
  p=dict(changed_membership_veto=False,scope='price_recommendations',owner_source='codex_owner_2026-11-16')
  self.assertTrue(membership_override(self.worker(p),{'status':'membership_changed'}))
  for status in ('growing','incomplete','not_growing'):
   self.assertFalse(membership_override(self.worker(p),{'status':status}))
 def test_negative_profit_remains_blocked(self):
  p=dict(current_cny=100,base_cny=200,discount=50);c=dict(current_cny=110,base_cny=220,discount=50)
  b=dict(expected_profit_per_day=50,orders_per_day=1,views=100,days=1)
  a=dict(advertising_per_day=1000,orders_per_day=0,views=100,days=1)
  r=choose_target(p,c,b,a,buyout_probability=.4,retention=.72,cost=500,dispatch=30,fx=12)
  self.assertNotEqual(r['status'],'recommended')
if __name__=='__main__':unittest.main()

