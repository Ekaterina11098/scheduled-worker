import copy,sys,types,unittest
from unittest.mock import patch
from china_advertising_decision_contract import finalize
class IO:
 def __init__(self):self.values={}
 def get(self,k):return copy.deepcopy(self.values.get(k))
 def create(self,k,v):self.values[k]=copy.deepcopy(v);return True
 def put(self,k,v):self.values[k]=copy.deepcopy(v)
def bundle(action=None):
 r=dict(nm=1,article='one',decision='Exclude at minimum. Old verified metrics',reason='Verified economics',action=action,decision_window=dict(days=['2026-11-18'],metrics=dict(spend=1)))
 return dict(day='2026-11-19',days=['2026-11-18'],campaigns=[dict(id=10,status=9,focus=[r])])
class CanonicalWording(unittest.TestCase):
 def run_final(self,io,b):
  modules={'china_advertising_economic_review':types.SimpleNamespace(apply=lambda b,s,m:copy.deepcopy(b)),'china_advertising_directions':types.SimpleNamespace(attach=lambda b,s:b)}
  with patch.dict(sys.modules,modules):return finalize(io,b,{}, {})
 def test_same_exact_action_retains_canonical_wording_and_reason(self):
  io=IO();a=dict(kind='ad_set_bid',target_minor=28)
  self.run_final(io,bundle(a));b=bundle(a);b['campaigns'][0]['focus'][0].update(decision='Exclude at minimum. Refreshed presentation',reason='Other wording')
  out=self.run_final(io,b);r=out['campaigns'][0]['attention'][0]
  self.assertEqual('Exclude at minimum. Old verified metrics',r['decision']);self.assertEqual('Verified economics',r['reason'])
 def test_changed_bid_on_same_facts_still_blocks(self):
  io=IO();self.run_final(io,bundle(dict(kind='ad_set_bid',target_minor=28)))
  with self.assertRaisesRegex(ValueError,'conflicting recommendation: 10:1'):self.run_final(io,bundle(dict(kind='ad_set_bid',target_minor=30)))
 def test_added_action_on_same_facts_still_blocks(self):
  io=IO();self.run_final(io,bundle())
  with self.assertRaises(ValueError):self.run_final(io,bundle(dict(kind='ad_exclude_sku')))
 def test_pending_first_full_day_without_action_keeps_canonical_wait(self):
  io=IO();b=bundle();r=b['campaigns'][0]['focus'][0];r.update(pending_first_day=True,decision_window=dict(days=[],metrics=dict(spend=0)),decision='Check completed-day spend')
  self.run_final(io,b);r['decision']='Wait for next full day'
  out=self.run_final(io,b);self.assertEqual('Check completed-day spend',out['campaigns'][0]['focus'][0]['decision']);self.assertEqual([],out['campaigns'][0]['attention'])
 def test_unexplained_no_action_verdict_change_still_blocks(self):
  io=IO();self.run_final(io,bundle());b=bundle();b['campaigns'][0]['focus'][0]['decision']='Opposite judgment'
  with self.assertRaises(ValueError):self.run_final(io,b)
 def test_new_facts_can_change_recommendation(self):
  io=IO();self.run_final(io,bundle());b=bundle(dict(kind='ad_exclude_sku'));b['campaigns'][0]['focus'][0]['current_bid_minor']=28
  self.assertEqual('ad_exclude_sku',self.run_final(io,b)['campaigns'][0]['attention'][0]['action']['kind'])
class CurrentStateIdentity(unittest.TestCase):
 def evaluate(self,io,b,bid):
  source=dict(batches={'0':dict(campaigns=dict(adverts=[dict(id=10,status=9,settings=dict(placements=dict(recommendations=True,search=False)),nm_settings=[dict(nm_id=1,bids_kopecks=dict(recommendations=bid,search=0))])]))})
  modules={'china_advertising_economic_review':types.SimpleNamespace(apply=lambda b,s,m:copy.deepcopy(b)),'china_advertising_directions':types.SimpleNamespace(attach=lambda b,s:b)}
  with patch.dict(sys.modules,modules):return finalize(io,b,source,{})
 def test_verified_bid_change_invalidates_old_recommendation_identity(self):
  io=IO();first=bundle(dict(kind='ad_set_bid',old_minor=32,target_minor=34));a=self.evaluate(io,first,32)
  next_=bundle();next_['campaigns'][0]['focus'][0]['decision']='Already changed; wait for first full day'
  b=self.evaluate(io,next_,34)
  self.assertNotEqual(a['decision_contract']['rows'][0]['facts_sha256'],b['decision_contract']['rows'][0]['facts_sha256'])
  self.assertIsNone(b['decision_contract']['rows'][0]['action'])
 def test_same_verified_bid_still_rejects_conflicting_action(self):
  io=IO();self.evaluate(io,bundle(dict(kind='ad_set_bid',old_minor=32,target_minor=34)),32)
  with self.assertRaisesRegex(ValueError,'conflicting recommendation'):self.evaluate(io,bundle(),32)
class UnresolvedToday(unittest.TestCase):
 def test_same_day_uncertain_bid_blocks_new_proposal_without_claiming_execution(self):
  from china_advertising_decision_contract import unresolved_bid_today
  source=dict(executions=[dict(payload=dict(items=[dict(status='uncertain',submitted_at='2026-11-23T05:44:00+00:00',request=dict(path='/api/advert/v1/bids',body=dict(bids=[dict(advert_id=40933588,nm_bids=[dict(nm_id=1473244345,bid_kopecks=34,placement='recommendations')])])))]))])
  self.assertEqual(1,len(unresolved_bid_today(source,40933588,1473244345,'2026-11-23')))
  self.assertEqual([],unresolved_bid_today(source,40933588,1473244345,'2026-11-24'))
  self.assertEqual([],unresolved_bid_today(source,40933588,99,'2026-11-23'))
if __name__=='__main__':unittest.main()
