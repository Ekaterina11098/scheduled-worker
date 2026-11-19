import copy,sys,types,unittest
from unittest.mock import patch
from china_advertising_decision_contract import finalize

class RepeatedEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.db={}
  class IO:
   def get(_,k):return copy.deepcopy(self.db.get(k))
   def put(_,k,v):self.db[k]=copy.deepcopy(v)
   def create(_,k,v):self.db[k]=copy.deepcopy(v);return True
  self.io=IO()
  self.action=dict(kind='ad_set_bid',campaign_id=1,nm_id=2,old_minor=28,target_minor=30,growth_evidence=dict(observed_at='2026-11-19T04:00:00Z',expected_margin_before_ads_cny=35,period_to='2026-11-18'))
  self.bundle=dict(day='2026-11-19',days=['2026-11-18'],campaigns=[dict(id=1,status=9,focus=[dict(nm=2,article='fixture',decision='Повысить 0.28 → 0.30',decision_window={'days':['2026-11-18']},action=self.action)])])
  economic=types.ModuleType('china_advertising_economic_review');economic.apply=lambda b,*a:copy.deepcopy(b)
  directions=types.ModuleType('china_advertising_directions');directions.attach=lambda b,*a:b
  self.patch=patch.dict(sys.modules,{'china_advertising_economic_review':economic,'china_advertising_directions':directions});self.patch.start();self.addCleanup(self.patch.stop)
  finalize(self.io,self.bundle,{},{});self.baseline=copy.deepcopy(self.db)
 def test_repeated_observation_keeps_same_recommendation(self):
  self.action['growth_evidence']['observed_at']='2026-11-19T05:00:00Z'
  out=finalize(self.io,self.bundle,{},{});self.assertEqual(out['campaigns'][0]['focus'][0]['action']['target_minor'],30)
 def test_different_bid_remains_blocked_and_ledger_unchanged(self):
  self.action['target_minor']=31
  with self.assertRaisesRegex(ValueError,'conflicting recommendation'):finalize(self.io,self.bundle,{},{})
  self.assertEqual(self.db,self.baseline)
 def test_different_economic_evidence_remains_blocked(self):
  self.action['growth_evidence']['expected_margin_before_ads_cny']=-1
  with self.assertRaisesRegex(ValueError,'conflicting recommendation'):finalize(self.io,self.bundle,{},{})
 def test_different_period_remains_blocked(self):
  self.action['growth_evidence']['period_to']='2026-11-17'
  with self.assertRaisesRegex(ValueError,'conflicting recommendation'):finalize(self.io,self.bundle,{},{})
 def test_changed_decision_remains_blocked(self):
  self.bundle['campaigns'][0]['focus'][0]['decision']='Исключить'
  with self.assertRaisesRegex(ValueError,'conflicting recommendation'):finalize(self.io,self.bundle,{},{})
if __name__=='__main__':unittest.main()

