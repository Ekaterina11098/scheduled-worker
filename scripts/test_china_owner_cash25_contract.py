import copy,hashlib,json,sys,types,unittest
from unittest.mock import patch
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
with patch.dict(sys.modules,{'china_loss_control':types.SimpleNamespace(digest=digest)}):
 import china_owner_cash25_contract as m
class Tests(unittest.TestCase):
 def setUp(self):
  self.item=dict(id='cash1',kind='topup_campaign',campaign_id=41155909,amount_cny=200,nm_ids=[1],
    owner_cash25_contract=m.ROOT+':contract:41155909',budget_evidence=dict(expected_bids={'1':dict(recommendations=27,search=0)},member_inputs={'1':dict(article='119',price=240)}))
  class IO:
   def get(self,k):return copy.deepcopy(self.data.get(k))
  self.io=IO();self.io.daily_report_plan=dict(items=[copy.deepcopy(self.item)]);self.io.daily_report_approval=dict(sender_id=42)
  self.io.data={m.ROOT+':owner_request':dict(status='approved_for_publication_only',total_cny=4800),
   self.item['owner_cash25_contract']:dict(status='ready_for_human_confirmation',grants_action_permission=False,
    campaign_id=41155909,action_sha256=digest([self.item]),maximum_funding_cny=200,
    risk_disclosed_before_confirmation=True,period_to='2026-11-24',required_actions=[])}
  self.before=dict(id=41155909,status=9,currency='CNY',nm_settings=[dict(nm_id=1,bids_kopecks=dict(recommendations=27,search=0))])
 def check(self):
  with patch.dict(sys.modules,{'china_loss_control':types.SimpleNamespace(digest=digest)}):return m.check(self.io,self.item,self.before)
 def test_exact_disclosed_cash_scope_accepted_without_fake_positive_profit(self):self.check()
 def test_changed_amount_rejected(self):
  self.item['amount_cny']=250
  with self.assertRaises(ValueError):self.check()
 def test_paused_campaign_cannot_be_resumed_or_funded(self):
  self.before['status']=11
  with self.assertRaises(ValueError):self.check()
 def test_owner_hold_preserved(self):
  self.io.data['china_agent:budget_owner_policy:v1']=dict(do_not_fund={'41155909':'hold'})
  with self.assertRaises(ValueError):self.check()
 def test_human_confirmation_required(self):
  self.io.daily_report_approval={}
  with self.assertRaises(ValueError):self.check()
 def test_required_advertising_changes_cannot_be_skipped(self):
  self.io.data[self.item['owner_cash25_contract']]['required_actions']=[dict(id='cut',kind='ad_set_bid',nm_id=1,placement='recommendations',target_minor=21)]
  with self.assertRaises(ValueError):self.check()
 def test_wrong_currency_rejected(self):
  self.before['currency']='RUB'
  with self.assertRaises(ValueError):self.check()
 def test_forged_action_rejected(self):
  self.io.daily_report_plan['items'][0]['amount_cny']=250
  with self.assertRaises(ValueError):self.check()
 def test_wrong_request_does_not_allow_funding(self):
  self.io.data[m.ROOT+':owner_request']['status']='draft'
  with self.assertRaises(ValueError):self.check()
 def test_fresh_price_change_rejected(self):
  modules={'china_loss_control':types.SimpleNamespace(digest=digest),
   'china_morning_readiness':types.SimpleNamespace(current_prices=lambda *a:dict(rows=[dict(nm_id=1,article='119',seller_price=250)]))}
  with patch.dict(sys.modules,modules),self.assertRaises(ValueError):m.validate(self.io,self.item,self.before)
 def test_matching_fresh_price_returns_nonprofit_cash_evidence(self):
  modules={'china_loss_control':types.SimpleNamespace(digest=digest),
   'china_morning_readiness':types.SimpleNamespace(current_prices=lambda *a:dict(rows=[dict(nm_id=1,article='119',seller_price=240)]))}
  with patch.dict(sys.modules,modules):got=m.validate(self.io,self.item,self.before)
  self.assertFalse(got['profit_proven']);self.assertEqual(got['amount_cny'],200)
 def test_executor_validator_uses_exact_cash_contract_branch(self):
  import china_budget_ready_model
  with patch.dict(sys.modules,{'china_owner_cash25_contract':types.SimpleNamespace(validate=lambda *a:dict(scoped=True))}):
   self.assertEqual(china_budget_ready_model.validate_funding(self.io,self.item,self.before),dict(scoped=True))
if __name__=='__main__':unittest.main()

