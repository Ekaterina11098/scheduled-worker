import copy,sys,types,unittest
from unittest.mock import patch
from china_advertising_decision_contract import effective_launch_at,changed_day
from china_budget_reserve import attach_completed_evidence,apply

class BudgetClockLaunchTests(unittest.TestCase):
 def setUp(self):
  self.state=dict(id=12,status=9,currency='CNY',settings={'placements':{'search':True,'recommendations':False}},timestamps={'started':'2026-11-18T22:26:00+03:00'},nm_settings=[{'nm_id':2,'bids_kopecks':{'search':28,'recommendations':0}}])
  initial=copy.deepcopy(self.state);initial['timestamps']['started']='2026-11-17T11:34:00+03:00'
  draft=copy.deepcopy(initial);draft['status']=4;draft['timestamps']['started']=None
  self.source=dict(observed_at='2026-11-19T04:00:00Z',budget_balance_observed_at_iso='2026-11-19T05:00:00Z',period_from='2026-11-12',period_to='2026-11-18',ids=[12],executions=[dict(payload=dict(status='verified',before=draft,after=initial))],batches={'0':dict(campaigns={'adverts':[self.state]},stats=[dict(advertId=12,days=[dict(date=d+'T00:00:00Z',sum=10,sum_price=200,orders=1,apps=[])for d in('2026-11-16','2026-11-17','2026-11-18')])])})
  self.bundle=dict(campaigns=[dict(id=12,name='fixture',status=9,balance=5,focus=[])])
 def test_new_balance_does_not_invalidate_completed_reserve(self):
  reason=types.ModuleType('china_campaign_pause_reason');reason.classify=lambda *a:{}
  with patch.dict(sys.modules,{'china_campaign_pause_reason':reason}):b=attach_completed_evidence(self.bundle,self.source,[])
  self.assertEqual(b['budget_observed_at'],'2026-11-19T05:00:00+00:00');self.assertEqual(b['budget_days'],['2026-11-16','2026-11-17','2026-11-18'])
  out=apply(b);self.assertNotEqual(out['campaigns'][0]['budget_audit_state'],'data_blocked');self.assertEqual(out['campaigns'][0]['budget_cash_gap'],25)
 def test_matching_original_launch_survives_status_resume(self):
  self.assertEqual(effective_launch_at(self.source,self.state),'2026-11-17T11:34:00+03:00')
 def test_changed_inventory_cannot_reuse_old_launch_anchor(self):
  self.state['nm_settings'].append({'nm_id':3,'bids_kopecks':{'search':28}})
  self.assertEqual(effective_launch_at(self.source,self.state),'2026-11-18T22:26:00+03:00')
 def test_changed_bid_cannot_reuse_old_launch_anchor(self):
  self.state['nm_settings'][0]['bids_kopecks']['search']=30
  self.assertEqual(effective_launch_at(self.source,self.state),'2026-11-18T22:26:00+03:00')
if __name__=='__main__':unittest.main()

