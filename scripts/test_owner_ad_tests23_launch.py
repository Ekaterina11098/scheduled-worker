import copy,datetime,sys,types,unittest
from unittest.mock import Mock,patch
if 'requests'not in sys.modules:
 try:import requests
 except ImportError:sys.modules['requests']=types.SimpleNamespace(request=Mock(),RequestException=RuntimeError)
import owner_ad_tests23_launch as m
class Funds(unittest.TestCase):
 def worker(self,budgets,error=None,wallet=5000):
  c=object.__new__(m.Client);c.item=dict(campaign_id=42139004,currency='RUB');c.state={'steps':{},'initial_budget_verified':0,'settings_verified':True};c.save=Mock();c.budget=Mock(side_effect=budgets)
  def call(path,method='GET',body=None,params=None,step=None):
   if path=='/adv/v1/balance':return dict(currency='RUB',net=wallet)
   if step=='deposit1000'and error:raise error
   return {'total':body['sum']}
  c.call=Mock(side_effect=call);return c
 def test_success_1000_never_adds_2000(self):
  c=self.worker([]);c.fund();self.assertEqual(c.state['budget'],1000);c.budget.assert_not_called()
  self.assertEqual([x.kwargs.get('step')for x in c.call.call_args_list if x.kwargs.get('step')],['deposit1000'])
 def test_2000_replaces_explicitly_rejected_1000_after_proving_zero_balance(self):
  c=self.worker([],m.Rejected(400,{'message':'minimum deposit is 2000'}));c.fund()
  self.assertEqual(c.state['budget'],2000);self.assertTrue(c.state['fallback_minimum_rejection_verified'])
  self.assertEqual([x.args[2]['sum']for x in c.call.call_args_list if x.kwargs.get('step')],[1000,2000])
 def test_unrelated_400_and_rate_limit_never_raise_budget(self):
  for e in [m.Rejected(400,{'message':'wrong currency'}),m.Rejected(429,{'message':'Too many requests'})]:
   c=self.worker([0],e)
   with self.assertRaises(m.Rejected):c.fund()
   self.assertFalse(c.state.get('fallback_minimum_rejection_verified'))
 def test_unknown_outcome_never_causes_fallback(self):
  c=self.worker([0],RuntimeError('uncertain'))
  with self.assertRaises(RuntimeError):c.fund()
  self.assertFalse(c.state.get('fallback_minimum_rejection_verified'))
 def test_nonzero_initial_budget_prevents_deposit(self):
  c=self.worker([]);c.state['initial_budget_verified']=1000
  with self.assertRaises(ValueError):c.fund()
  self.assertFalse(c.state.get('fallback_minimum_rejection_verified'))
 def test_unexpected_successful_total_stops_without_additional_funding(self):
  c=self.worker([]);c.call.side_effect=lambda path,*a,**kw:dict(currency='RUB',net=5000)if path=='/adv/v1/balance'else{'total':3000}
  with self.assertRaises(RuntimeError):c.fund()
  self.assertFalse(c.state.get('fallback_minimum_rejection_verified'))
 def test_insufficient_wallet_does_not_charge_card_or_try_larger_amount(self):
  c=self.worker([],wallet=999)
  with self.assertRaises(ValueError):c.fund()
  self.assertFalse(any(x.kwargs.get('step')for x in c.call.call_args_list))
class Boundaries(unittest.TestCase):
 def test_cache_preserves_original_source_time_and_rejects_stale_or_wrong_sku(self):
  now=datetime.datetime.now(datetime.timezone.utc);observed=(now-datetime.timedelta(minutes=20)).isoformat()
  item={'cabinet':'token_2','skus':[{'nm':1,'article':'A'}]}
  product=dict(nmId=1,vendorCode='A',subjectId=50,stocks={'wb':5},feedbackRating=5)
  values={m.ROOT+':launch:token_2':dict(stock_readback={'1':product},stock_verified_at=observed)}
  db=Mock();db.get.side_effect=lambda k:copy.deepcopy(values.get(k))
  got=m.stock_cache(db,item,now);self.assertEqual(got[1],observed)
  values[m.ROOT+':launch:token_2']['stock_verified_at']=(now-datetime.timedelta(minutes=91)).isoformat()
  self.assertIsNone(m.stock_cache(db,item,now))
  values[m.ROOT+':launch:token_2']['stock_verified_at']=observed;product['vendorCode']='wrong'
  self.assertIsNone(m.stock_cache(db,item,now))
 def test_durable_journal_compares_json_wire_representation(self):
  c=object.__new__(m.Client);c.state={'stock':{123:{'wb':5}}};c.key='private-key'
  class DB:
   def put(self,k,v):self.saved=m.json.loads(m.json.dumps(v))
   def get(self,k):return self.saved
  c.db=DB();c.save();self.assertEqual(c.db.get(c.key),{'stock':{'123':{'wb':5}}})
 def test_minimum_bid_currency_and_coverage(self):
  item={'currency':'KGS','skus':[{'nm':1}]};v={'bids':[{'nm_id':1,'bids':[{'type':'search','currency':'RUB','value':325}]}]}
  with self.assertRaises(ValueError):m.parse_bids(v,item)
  v['bids'][0]['bids'][0]['currency']='KGS';self.assertEqual(m.parse_bids(v,item),{1:325})
  with self.assertRaises(ValueError):m.parse_bids({'bids':v['bids']*2},item)
 def test_existing_campaign_or_unverified_start_is_forbidden(self):
  c=object.__new__(m.Client);c.item={'campaign_id':42139004};c.state={}
  with self.assertRaises(PermissionError):c.check_request('/adv/v0/start','GET',None,{'id':42139004},'start')
  c.state={'funding_verified':True,'settings_verified':True}
  with self.assertRaises(PermissionError):c.check_request('/adv/v0/start','GET',None,{'id':36514081},'start')
  with self.assertRaises(PermissionError):c.check_request('/adv/v2/seacat/save-ad','POST',{},None,'create')
  with self.assertRaises(PermissionError):c.check_request('/adv/v1/budget/deposit','POST',{'sum':2000,'type':1,'return':True},{'id':42139004},'deposit2000')
if __name__=='__main__':unittest.main()
