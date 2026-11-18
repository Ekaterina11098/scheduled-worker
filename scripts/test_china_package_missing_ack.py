import copy,unittest
from china_package_readback import validate
class MissingAcknowledgement(unittest.TestCase):
 def test_two_reads_do_not_fabricate_missing_receipt(self):
  before=dict(id=12,currency='CNY',status=9,settings={},nm_settings=[dict(nm_id=1,bids_kopecks={'recommendations':40})])
  after=copy.deepcopy(before);after['nm_settings'][0]['bids_kopecks']['recommendations']=28
  item=dict(id='12:1',kind='ad_set_bid',campaign_id=12,nm_id=1,placement='recommendations',old_minor=40,target_minor=28)
  state=dict(id='12:1',status='uncertain',before=before,request={'method':'PATCH'})
  states=[state];result=validate([item],states,lambda cid:copy.deepcopy(after),pause=lambda _:None)
  self.assertEqual(result['status'],'uncertain')
  self.assertEqual(len(result['rounds']),2)
  self.assertEqual(states,[state])
  self.assertNotIn('response',states[0])
  self.assertNotIn('submitted_at',states[0])
  self.assertEqual(result['reconciled_item_ids'],[])
 def test_individually_verified_readback_does_not_replay(self):
  before=dict(id=12,currency='CNY',status=9,settings={},nm_settings=[dict(nm_id=1,bids_kopecks={'recommendations':40})])
  after=copy.deepcopy(before);after['nm_settings'][0]['bids_kopecks']['recommendations']=28
  item=dict(id='12:1',kind='ad_set_bid',campaign_id=12,nm_id=1,placement='recommendations',old_minor=40,target_minor=28)
  states=[dict(id='12:1',status='verified',before=before,after=after,request={'method':'PATCH'})]
  self.assertEqual(validate([item],states,lambda cid:copy.deepcopy(after),pause=lambda _:None)['status'],'verified')
if __name__=='__main__':unittest.main()
