import unittest
from china_advertising_directions import attach

class RaiseAdditionOverlap(unittest.TestCase):
 def source(self):
  return dict(period_to='2026-11-19',catalogue=dict(rows=[dict(nmID=1473243896,vendorCode='046-NoelBag-blue')]),addition_scan=dict(status='complete',candidate_ids=[1473243896],period_from='2026-10-21',period_to='2026-11-19'),economics=dict(rows={'1473243896':dict(expected_margin_before_ads_cny=36.57,stock_free=889,sample_size=77)}))
 def bundle(self,kind='ad_set_bid',old=32,target=34,status=9):
  action=dict(kind=kind,nm_id=1473243896,old_minor=old,target_minor=target)
  return dict(campaigns=[dict(id=40933588,status=status,focus=[dict(nm=1473243896,article='046-NoelBag-blue',decision='Повысить',action=action)])])
 def test_ready_raise_is_not_recreated_as_incomplete_addition(self):
  result=attach(self.bundle(),self.source())['recommendation_directions']
  self.assertEqual(result['raise']['ready_count'],1)
  self.assertEqual(result['add']['rows'],[])
 def test_actual_unfinished_candidate_remains_visible_to_guard(self):
  result=attach(dict(campaigns=[]),self.source())['recommendation_directions']
  self.assertEqual(result['add']['unready_count'],1)
  self.assertFalse(result['add']['rows'][0]['ready'])
 def test_reduction_does_not_suppress_unfinished_addition(self):
  result=attach(self.bundle(old=34,target=32),self.source())['recommendation_directions']
  self.assertEqual(result['reduce']['ready_count'],1)
  self.assertEqual(result['add']['unready_count'],1)
 def test_paused_raise_cannot_suppress_candidate(self):
  result=attach(self.bundle(status=11),self.source())['recommendation_directions']
  self.assertEqual(result['raise']['ready_count'],0)
  self.assertEqual(result['add']['unready_count'],1)

if __name__=='__main__':unittest.main()

