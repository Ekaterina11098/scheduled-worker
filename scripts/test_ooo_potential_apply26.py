import copy,sys,types,unittest
sys.modules.setdefault('requests',types.SimpleNamespace(request=lambda *args,**kwargs:(_ for _ in()).throw(AssertionError('No network in offline tests'))))
class Stop(Exception):pass
sys.modules['ooo_report_executor']=types.SimpleNamespace(DB=object,Executor=object,Stop=Stop,Deferred=type('Deferred',(Exception,),{}),project=lambda c:c,stamp=lambda:'now',ROOT='test:')
from ooo_potential_apply26 import prepare,request_scope
class Guards(unittest.TestCase):
 def fixture(self):
  auth={'campaign':2,'keep_nm_ids':[1,2,3],'recommendations_minor':325,'deposit_kgs':1200,'resume':True,'readback_ids':[2,5]}
  baseline={'id':2,'status':11,'currency':'KGS','bid_type':'manual','settings':{'payment_type':'cpc','placements':{'search':False,'recommendations':True}},'restrictions':{'can_change_nms':True},'nm_settings':[{'nm_id':n,'bids_kopecks':{'search':0,'recommendations':325}}for n in(1,2,3,4)]}
  return auth,baseline
 def test_exact_three_only_and_no_unnecessary_bid_writes(self):
  a,b=self.fixture();e,deletes,bids=prepare(a,b)
  self.assertEqual({n['nm_id']for n in e['nm_settings']},{1,2,3});self.assertEqual(deletes,[4]);self.assertEqual(bids,[]);self.assertEqual(e['status'],9);self.assertEqual(b['status'],11)
 def test_missing_approved_member_stops(self):
  a,b=self.fixture();b['nm_settings'].pop(0)
  with self.assertRaises(Stop):prepare(a,b)
 def test_no_unapproved_funding_or_other_campaign(self):
  a,b=self.fixture();s={'delete_nm_ids':[4],'bid_changes':[]}
  for body,params in [({'sum':1201,'type':1,'return':True},{'id':2}),({'sum':1200,'type':1,'return':True},{'id':5})]:
   with self.assertRaises(Stop):request_scope(a,s,'POST','/adv/v1/budget/deposit',body,params)
 def test_exact_funding_allowed(self):
  a,b=self.fixture();request_scope(a,{},'POST','/adv/v1/budget/deposit',{'sum':1200,'type':1,'return':True},{'id':2})
 def test_other_campaign_memberships_blocked(self):
  a,b=self.fixture();s={'delete_nm_ids':[4]}
  with self.assertRaises(Stop):request_scope(a,s,'PATCH','/adv/v0/auction/nms',{'nms':[{'advert_id':5,'nms':{'add':[],'delete':[4]}}]},None)
 def test_search_and_other_placements_not_enabled(self):
  a,b=self.fixture();b['settings']['placements']['search']=True
  with self.assertRaises(Stop):prepare(a,b)
if __name__=='__main__':unittest.main()
