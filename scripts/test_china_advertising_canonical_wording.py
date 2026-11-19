import copy,sys,types,unittest
from unittest.mock import patch
from china_advertising_decision_contract import finalize
class IO:
 def __init__(self):self.values={}
 def get(self,k):return copy.deepcopy(self.values.get(k))
 def create(self,k,v):self.values[k]=copy.deepcopy(v);return True
 def put(self,k,v):self.values[k]=copy.deepcopy(v)
def bundle(action=None):
 r=dict(nm=1,article='one',decision='Keep canonical',reason='Verified economics',action=action,decision_window=dict(days=['2026-11-18'],metrics=dict(spend=1)))
 return dict(day='2026-11-19',days=['2026-11-18'],campaigns=[dict(id=10,status=9,focus=[r])])
class CanonicalWording(unittest.TestCase):
 def run_final(self,io,b):
  modules={'china_advertising_economic_review':types.SimpleNamespace(apply=lambda b,s,m:copy.deepcopy(b)),'china_advertising_directions':types.SimpleNamespace(attach=lambda b,s:b)}
  with patch.dict(sys.modules,modules):return finalize(io,b,{}, {})
 def test_same_exact_action_retains_canonical_wording_and_reason(self):
  io=IO();a=dict(kind='ad_set_bid',target_minor=28)
  self.run_final(io,bundle(a));b=bundle(a);b['campaigns'][0]['focus'][0].update(decision='Presentation rewrite',reason='Other wording')
  out=self.run_final(io,b);r=out['campaigns'][0]['attention'][0]
  self.assertEqual('Keep canonical',r['decision']);self.assertEqual('Verified economics',r['reason'])
 def test_changed_bid_on_same_facts_still_blocks(self):
  io=IO();self.run_final(io,bundle(dict(kind='ad_set_bid',target_minor=28)))
  with self.assertRaisesRegex(ValueError,'conflicting recommendation: 10:1'):self.run_final(io,bundle(dict(kind='ad_set_bid',target_minor=30)))
 def test_added_action_on_same_facts_still_blocks(self):
  io=IO();self.run_final(io,bundle())
  with self.assertRaises(ValueError):self.run_final(io,bundle(dict(kind='ad_exclude_sku')))
 def test_new_facts_can_change_recommendation(self):
  io=IO();self.run_final(io,bundle());b=bundle(dict(kind='ad_exclude_sku'));b['campaigns'][0]['focus'][0]['current_bid_minor']=28
  self.assertEqual('ad_exclude_sku',self.run_final(io,b)['campaigns'][0]['attention'][0]['action']['kind'])
if __name__=='__main__':unittest.main()
