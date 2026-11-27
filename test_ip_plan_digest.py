import copy,json,unittest
from ip_daily_png_contract import digest,plan_digest,plan_digest_matches
class NumericRoundtrip(unittest.TestCase):
 def setUp(self):
  self.actions=[{'kind':'remove','campaign':123,'nm':456,'analysis_metrics':{'orders':0,'clicks':53,'cr_pct':0.0},'daily':{'2026-11-26':{'spend':156}}}]
 def test_legacy_jsonb_zero(self):
  expected=digest(self.actions);restored=json.loads(json.dumps(self.actions).replace('0.0','0'))
  self.assertTrue(plan_digest_matches(restored,expected))
  self.assertEqual(plan_digest(restored),plan_digest(self.actions))
 def test_scope_and_evidence_tampering_fail(self):
  expected=digest(self.actions)
  for key,value in [('nm',457),('campaign',124),('kind','add')]:
   altered=copy.deepcopy(self.actions);altered[0][key]=value
   self.assertFalse(plan_digest_matches(altered,expected))
  altered=copy.deepcopy(self.actions);altered[0]['daily']['2026-11-26']['spend']=155
  self.assertFalse(plan_digest_matches(altered,expected))
if __name__=='__main__':unittest.main()
