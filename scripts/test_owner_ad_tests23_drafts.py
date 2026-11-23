import copy,datetime,sys,types,unittest
from unittest.mock import Mock,patch
if 'requests'not in sys.modules:
 try:import requests
 except ImportError:sys.modules['requests']=types.SimpleNamespace(request=Mock(),RequestException=RuntimeError)
import owner_ad_tests23_drafts as m
def fixture():
 item=dict(cabinet='token_2',currency='RUB',name='test',skus=[{'nm':1,'article':'A'}],auto_topup=False,payment_type='cpc',bid_type='manual',placements=['search'])
 plan=dict(status='approved_draft_and_quote',owner_id=5122667182,max_new_campaigns=2,items=[item,{}],expires_at=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat())
 pre=dict(identity_verified=True,finished_at=m.stamp(),stages={k:{'status':'complete'}for k in ['funnel','prices','campaigns','wallet']})
 pre['stages']['funnel']['data']={'data':{'products':[{'product':dict(nmId=1,vendorCode='A',subjectId=50,stocks={'wb':5},feedbackRating=5)}]}}
 pre['stages']['prices']['data']=[dict(nmID=1,vendorCode='A')];pre['stages']['campaigns']['data']=[]
 return plan,item,pre
class DB:
 def __init__(self):self.values={}
 def get(self,k):return copy.deepcopy(self.values.get(k))
 def put(self,k,v,**kw):self.values[k]=copy.deepcopy(v);return [v]
class Tests(unittest.TestCase):
 def test_stock_identity_and_active_duplicates_are_enforced(self):
  p,i,s=fixture();self.assertEqual(m.validate(p,i,s),[1])
  s['stages']['funnel']['data']['data']['products'][0]['product']['vendorCode']='other'
  with self.assertRaises(PermissionError):m.validate(p,i,s)
  p,i,s=fixture();s['stages']['campaigns']['data']=[dict(status=9,nm_settings=[{'nm_id':1}])]
  with self.assertRaises(PermissionError):m.validate(p,i,s)
 def worker(self):
  _,i,_=fixture();db=DB();state={'steps':{}}
  with patch.dict(m.os.environ,{'WB_TOKEN_2':'not-used'}):return m.Draft(db,i,state,'key')
 def test_only_exact_creation_is_permitted_and_deposits_cannot_be_sent(self):
  d=self.worker()
  with patch.object(m.requests,'request',side_effect=AssertionError('Network must not happen')):
   with self.assertRaises(PermissionError):d.call('/adv/v1/budget/deposit','POST',{'sum':1000,'type':1},step='deposit')
   with self.assertRaises(PermissionError):d.call('/adv/v0/start',params={'id':123})
   with self.assertRaises(PermissionError):d.call('/adv/v2/seacat/save-ad','POST',{'nms':[2]},step='create')
 def test_uncertain_creation_cannot_be_replayed(self):
  d=self.worker();d.state['steps']['create']={'status':'uncertain'}
  body=dict(name='test',nms=[1],bid_type='manual',payment_type='cpc',placement_types=['search'])
  with patch.object(m.requests,'request',side_effect=AssertionError('No duplicate')):
   with self.assertRaises(RuntimeError):d.call('/adv/v2/seacat/save-ad','POST',body,step='create')
 def test_accepted_creation_returns_original_id_without_another_call(self):
  d=self.worker();d.state['steps']['create']=dict(status='accepted',response=123)
  body=dict(name='test',nms=[1],bid_type='manual',payment_type='cpc',placement_types=['search'])
  with patch.object(m.requests,'request',side_effect=AssertionError('No duplicate')):self.assertEqual(d.call('/adv/v2/seacat/save-ad','POST',body,step='create'),123)
if __name__=='__main__':unittest.main()
