import sys,types,unittest,copy
from unittest.mock import patch
from china_completed_cost_scan import expand
class Scan(unittest.TestCase):
 def fixture(self):
  s=dict(catalogue=dict(rows=[dict(nmID=2,vendorCode='test')]),economics=dict(rows={'2':dict(expected_margin_before_ads_cny=10)}),executions=[],full_growth_inputs=dict(minimums={'1':dict(bids=[dict(nm_id=2,bids=[dict(value=28,currency='CNY')])])}),batches=dict(a=dict(campaigns=dict(adverts=[dict(id=1,status=9,settings=dict(payment_type='cpc'),timestamps=dict(started='2026-11-01T00:00:00+03:00'),nm_settings=[dict(nm_id=2)])]),stats=[dict(advertId=1,days=[dict(date='2026-11-14T00:00:00Z',apps=[dict(nms=[dict(nmId=2,sum=42,orders=0,sum_price=0,clicks=140,views=2000)])])])])))
  b=dict(day='2026-11-15',days=['2026-11-12','2026-11-13','2026-11-14'],campaigns=[dict(id=1,focus=[])])
  return b,s
 def run_scan(self,b,s,changes=[]):
  with patch.dict(sys.modules,{'china_advertising_v2':types.SimpleNamespace(history=lambda x:changes)}):
   minima={};r=expand(b,s,minima);return r,minima
 def test_risk_not_in_initial_shortlist_is_checked(self):
  b,s=self.fixture();r,m=self.run_scan(b,s);self.assertEqual(r['campaigns'][0]['focus'][0]['period']['spend'],42);self.assertEqual(m['1:2'],28);self.assertEqual(b['campaigns'][0]['focus'],[])
 def test_today_and_change_day_cannot_produce_action(self):
  b,s=self.fixture();r,m=self.run_scan(b,s,[dict(nm=2,cid=1,kind='bid',at='2026-11-14T01:00:00+03:00')]);self.assertEqual(r['campaigns'][0]['focus'],[])
 def test_existing_focus_not_duplicated(self):
  b,s=self.fixture();b['campaigns'][0]['focus']=[dict(nm=2)];r,m=self.run_scan(b,s);self.assertEqual(len(r['campaigns'][0]['focus']),1)
if __name__=='__main__':unittest.main()


