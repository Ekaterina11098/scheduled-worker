import copy,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from china_selected_campaign_test import validate_contract,execute,CONTRACT
from china_loss_control import digest

class IO:
 def __init__(self):self.rows={};self.daily_report_plan={}
 def get(self,k):return copy.deepcopy(self.rows.get(k))
 def put(self,k,v):self.rows[k]=copy.deepcopy(v)

def fixture():
 io=IO();before=dict(id=123,status=11,currency='CNY',bid_type='manual',settings=dict(payment_type='cpc'),restrictions=dict(can_change_nms=True),nm_settings=[dict(nm_id=n,bids_kopecks=dict(recommendations=b))for n,b in[(10,28),(11,28)]])
 now=datetime.now(timezone.utc);item=dict(id='synthetic',kind='recover_campaign',campaign_id=123,selected_test=True,nm_ids=[10,11],remove_nm_ids=[],placement='recommendations',target_minor=28,amount_cny=200,balance_before=0,review_scope_text='Exact two products, remove third; positive base, negative stress;200fundandresume',selected_test_contract=CONTRACT+'123:synthetic',requires_preparation_key='synthetic-prepared',recovery_evidence=dict(expected_bids={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']},period_to=(now-timedelta(days=2)).date().isoformat(),observed_at=now.isoformat(),preliminary=True,modeled_after_ads_cny=20,stress_after_ads_cny=-5,risk_disclosed_before_confirmation=True))
 io.rows['synthetic-prepared']=dict(status='verified',after=copy.deepcopy(before))
 io.rows[item['selected_test_contract']]=dict(status='ready_for_human_confirmation',grants_action_permission=False,action_sha256=digest([item]),expires_at=(now+timedelta(hours=1)).isoformat(),maximum_funding_cny=200)
 io.rows['china_agent:campaign_economics_routes:v1']=dict(campaigns={'123':dict(nm_ids=[10,11])})
 return io,before,item

class SelectedTest(unittest.TestCase):
 def test_frozen_contract_and_scope_cannot_be_expanded(self):
  io,b,i=fixture();validate_contract(io,i,b)
  for key,value in [('amount_cny',250),('nm_ids',[10,11,12]),('target_minor',60),('review_scope_text','')]:
   x=copy.deepcopy(i);x[key]=value
   with self.assertRaises(AssertionError):validate_contract(io,x,b)
  io.rows[i['selected_test_contract']]['grants_action_permission']=True
  with self.assertRaises(AssertionError):validate_contract(io,i,b)
 def test_funding_cannot_run_before_separate_ads_confirmation(self):
  io,b,i=fixture();io.rows['synthetic-prepared']['status']='ready_for_human_confirmation'
  with self.assertRaises(AssertionError):validate_contract(io,i,b)
 def test_changed_campaign_and_expired_proposal_fail(self):
  io,b,i=fixture();b['status']=9
  with self.assertRaises(AssertionError):validate_contract(io,i,b)
  b['status']=11;io.rows[i['selected_test_contract']]['expires_at']='2000-01-01T00:00:00+00:00'
  with self.assertRaises(AssertionError):validate_contract(io,i,b)
 def run_flow(self,fail=None):
  io,b,i=fixture();state={};writes=[];balance=[0]
  def campaign(cid):return copy.deepcopy(b)
  def req(path,method='GET',body=None):
   if path.endswith('/bids/min'):return dict(bids=[dict(nm_id=n,bids=[dict(value=28,currency='CNY',type='recommendation')])for n in[10,11]])
   if path.endswith('/budget'):return dict(adverts=[dict(advertId=123,currency='CNY'if balance[0]else'',total=balance[0])])
   if path.endswith('/config'):return dict(currency='CNY',minTopUp=10000)
   if path.endswith('/balance'):return dict(currency='CNY',balance=1000)
   writes.append(path)
   if fail and fail in path:raise RuntimeError('Synthetic uncertain response')
   if path.endswith('/nms'):b['nm_settings']=[n for n in b['nm_settings']if n['nm_id']in[10,11]]
   elif path.endswith('/bids'):
    for n in b['nm_settings']:n['bids_kopecks']['recommendations']=28
   elif '/deposit?'in path:balance[0]+=200
   elif '/start?'in path:b['status']=9
   else:raise AssertionError(path)
   return {}
  with patch('china_selected_campaign_test.current_economics',return_value={'modeled_after_ads_cny':20}),patch('china_daily_report_validity.require',return_value=None):
   if fail:
    with self.assertRaises(RuntimeError):execute(io,i,state,lambda:None,req,campaign,None)
   else:execute(io,i,state,lambda:None,req,campaign,None)
   with self.assertRaises(ValueError):execute(io,i,state,lambda:None,req,campaign,None)
  return state,writes,io,i
 def test_exact_order_readback_notice_and_no_repeat(self):
  s,w,io,i=self.run_flow();self.assertEqual(s['status'],'verified');self.assertEqual(len(w),2)
  self.assertIn('/deposit?',w[0]);self.assertIn('/start?',w[1])
  from china_execution_notice import proven
  self.assertTrue(proven(i,s));bad=copy.deepcopy(s);bad['after']['nm_settings'].append(dict(nm_id=12,bids_kopecks=dict(recommendations=50)));self.assertFalse(proven(i,bad))
  self.assertEqual(io.rows['china_agent:campaign_economics_routes:v1']['campaigns']['123']['nm_ids'],[10,11])
 def test_uncertain_funding_cannot_resume(self):
  s,w,_,_=self.run_flow(fail='/deposit?');self.assertEqual(s['status'],'uncertain');self.assertEqual(len(w),1);self.assertFalse(any('/start?'in x for x in w))
if __name__=='__main__':unittest.main()
