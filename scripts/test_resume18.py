import unittest,copy
from china_advertising_decision_contract import effective_launch_at,changed_day
from china_advertising_v2 import compact_execution_records
class Tests(unittest.TestCase):
 def setUp(self):
  self.old=dict(id=41332083,status=11,currency='CNY',settings=dict(placements=dict(search=True,recommendations=False)),timestamps=dict(started='2026-11-09T12:00:00+03:00'),nm_settings=[dict(nm_id=1,bids_kopecks=dict(search=28,recommendations=0))])
  self.new=copy.deepcopy(self.old);self.new.update(status=9,timestamps=dict(started='2026-11-17T10:35:41+03:00'))
  self.rec=dict(payload=dict(status='done',items=[dict(id='manual-continuation:41332083:test',status='verified',before=self.old,after=self.new,verified_at='2026-11-17T07:35:49+00:00')]))
 def test_cash_resume_keeps_previous_launch(self):self.assertEqual(effective_launch_at(dict(executions=[self.rec]),self.new),self.old['timestamps']['started'])
 def test_compaction_preserves_proof(self):
  source=dict(executions=compact_execution_records([self.rec]))
  self.assertEqual(effective_launch_at(source,self.new),self.old['timestamps']['started'])
  self.assertEqual(changed_day(source,self.new,1),'2026-11-09')
 def test_actual_new_campaign_retains_launch(self):self.assertEqual(effective_launch_at(dict(executions=[]),self.new),self.new['timestamps']['started'])
 def test_changed_bid_is_not_cash_only(self):
  rec=copy.deepcopy(self.rec);rec['payload']['items'][0]['before']['nm_settings'][0]['bids_kopecks']['search']=34
  self.assertEqual(effective_launch_at(dict(executions=[rec]),self.new),self.new['timestamps']['started'])
 def test_selected_composition_test_not_reinterpreted(self):
  rec=copy.deepcopy(self.rec);rec['payload']['items'][0]['selected_test']=True
  self.assertEqual(effective_launch_at(dict(executions=[rec]),self.new),self.new['timestamps']['started'])
 def test_real_price_change_still_resets_sku_window(self):
  rec=dict(payload=dict(status='done',completed_at='2026-11-17T15:00:00+00:00',items=[dict(status='applied',selection=dict(nm_id='1',current_cny='100',target_cny='95'),request=dict(nmID=1,price=190,discount=50),readback=dict(nmID=1,currencyIsoCode4217='CNY',discount=50,sizes=[dict(price=190,discountedPrice=95)]))]))
  self.assertEqual(changed_day(dict(executions=[self.rec,rec]),self.new,1),'2026-11-17')
if __name__=='__main__':unittest.main()
