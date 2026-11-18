import copy,unittest
from china_package_proof import reconcile,proves
class Tests(unittest.TestCase):
 def setUp(self):
  self.base=dict(id=1,currency='CNY',status=9,settings={'x':1},nm_settings=[dict(nm_id=10,subject={'id':50},bids_kopecks={'search':30})])
  self.items=[dict(id='cut',kind='ad_set_bid',campaign_id=1,nm_id=10,placement='search',target_minor=28),dict(id='add',kind='ad_add_sku',campaign_id=1,nm_id=11,subject_id=50,placement='search',target_minor=28)]
  self.after=copy.deepcopy(self.base);self.after['nm_settings'][0]['bids_kopecks']['search']=28;self.after['nm_settings'].append(dict(nm_id=11,subject={'id':50},bids_kopecks={'search':28}))
  self.states=[dict(id=i['id'],status='uncertain',before=copy.deepcopy(self.base),after=copy.deepcopy(self.after),request={'method':'PATCH'},response={},submitted_at='2026-11-18T06:00:00+00:00')for i in self.items]
  self.rounds=[dict(campaigns={'1':copy.deepcopy(self.after)})for _ in range(2)]
 def test_compound_readbacks_reconcile_without_writes(self):
  self.assertEqual(reconcile(self.items,self.states,self.rounds),['cut','add']);self.assertTrue(all(proves(i,s)for i,s in zip(self.items,self.states)))
 def test_unsubmitted_cannot_be_promoted(self):
  self.states[0].pop('response')
  with self.assertRaises(ValueError):reconcile(self.items,self.states,self.rounds)
 def test_unapproved_extra_member_rejected(self):
  self.rounds[1]['campaigns']['1']['nm_settings'].append(dict(nm_id=99,bids_kopecks={'search':28}))
  with self.assertRaises(ValueError):reconcile(self.items,self.states,self.rounds)
 def test_wrong_bid_rejected(self):
  self.rounds[1]['campaigns']['1']['nm_settings'][0]['bids_kopecks']['search']=29
  with self.assertRaises(ValueError):reconcile(self.items,self.states,self.rounds)
 def test_proof_cannot_cover_another_action(self):
  reconcile(self.items,self.states,self.rounds);i=copy.deepcopy(self.items[0]);i['target_minor']=29;self.assertFalse(proves(i,self.states[0]))
if __name__=='__main__':unittest.main()
