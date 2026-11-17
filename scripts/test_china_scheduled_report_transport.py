import copy,sys,unittest,types
from datetime import date,datetime,timezone,timedelta
from unittest.mock import patch
from china_scheduled_price_release import release_time,wait_for_release
from china_report_preflight import freeze_contracts,stage_restarts
from china_loss_control import digest
from china_confirmed_report_recovery import retryable,recheck
class IO:
 def __init__(self):self.rows={}
 def get(self,k):return copy.deepcopy(self.rows.get(k))
 def create(self,k,v):self.rows[k]=copy.deepcopy(v);return True
 def put(self,k,v):self.rows[k]=copy.deepcopy(v)
class Transport(unittest.TestCase):
 def test_release_uses_actual_day_and_moscow_time(self):
  self.assertEqual(release_time(date(2026,11,18)).isoformat(),'2026-11-18T10:30:00+03:00')
  self.assertEqual(release_time(date(2026,11,18),'intraday').hour,15)
 def test_owner_hold_is_rechecked_before_transport(self):
  now=datetime.now(timezone.utc);day=now.astimezone(release_time(date.today()).tzinfo).date()
  w=types.SimpleNamespace(day=day,scheduled_release_at=now-timedelta(seconds=1),audit={},get=lambda k:dict(status='held_by_owner',owner_id=5122667182))
  with self.assertRaises(RuntimeError):wait_for_release(w)
 def test_staging_extends_exact_lease_then_waits_without_model_or_send(self):
  start=datetime(2026,11,18,7,20,tzinfo=timezone.utc);target=release_time(date(2026,11,18));clock=[start];writes=[]
  class Clock:
   @staticmethod
   def now(tz=None):return clock[0].astimezone(tz)
  w=types.SimpleNamespace(day=date(2026,11,18),mode='morning',job={'id':123},scheduled_release_at=target,audit={},get=lambda k:None,patch=lambda v:writes.append(v)or[{}],save=lambda *a:None)
  with patch('china_scheduled_price_release.datetime',Clock),patch('china_scheduled_price_release.time.sleep',side_effect=lambda s:clock.__setitem__(0,clock[0]+timedelta(seconds=s))):wait_for_release(w)
  self.assertEqual(clock[0],target);self.assertEqual(len(writes),1)
 def action(self):return dict(id='test',kind='recover_campaign',campaign_id=123,selection_family='budgets',amount_cny=200,selected_test_contract='contract',recovery_evidence=dict(modeled_after_ads_cny=1,risk_disclosed_before_confirmation=True))
 def test_rendered_family_is_bound_without_losing_float_identity(self):
  io=IO();a=self.action();a['recovery_evidence']['zero']=0.0;raw=copy.deepcopy(a);raw.pop('selection_family')
  io.rows['contract']=dict(status='ready_for_human_confirmation',grants_action_permission=False,maximum_funding_cny=200,action_sha256=digest([raw]))
  freeze_contracts(io,[dict(family='budgets',actions=[a])]);self.assertEqual(io.rows['contract']['action_sha256'],digest([a]))
  bad=copy.deepcopy(a);bad['amount_cny']=250
  with self.assertRaises(ValueError):freeze_contracts(io,[dict(family='budgets',actions=[bad])])
 def test_wrong_report_and_duplicate_action_are_rejected(self):
  for pages in ([dict(family='drr',actions=[self.action()])],[dict(family='budgets',actions=[self.action(),self.action()])]):
   with self.assertRaises(ValueError):freeze_contracts(IO(),pages)
 def test_restart_rates_and_funding_use_separate_confirmations(self):
  io=IO();a=dict(kind='recover_campaign',campaign_id=123,status_before=11,placement='search',target_minor=28,amount_cny=100,recovery_evidence=dict(expected_bids={'10':{'search':35}},member_inputs={'10':{'article':'a'}}))
  b=stage_restarts(io,dict(day='2026-11-18',campaigns=[dict(id=123,financial_action=a,focus=[])]));c=b['campaigns'][0]
  self.assertEqual(c['focus'][0]['action']['target_minor'],28);self.assertEqual(c['focus'][0]['action']['old_minor'],35)
  budget=c['financial_action'];self.assertTrue(budget['keep_existing_bids']);self.assertEqual(budget['selection_family'],'budgets');self.assertEqual(budget['requires_preparation_key'],c['focus'][0]['action']['preparation_ref'])
  freeze_contracts(io,[dict(family='drr',actions=[c['focus'][0]['action']]),dict(family='budgets',actions=[dict(budget,id='fund')])],b['proposal_preparation_contracts'])
 def test_only_unsubmitted_transient_preflight_can_retry(self):
  s=dict(id='a',status='blocked',reason='ConnectTimeout');self.assertTrue(retryable(s));recheck(s);self.assertEqual(len(s['preflight_failures']),1)
  for change in(dict(status='uncertain'),dict(request={'path':'fund'}),dict(steps=[{'status':'submitting'}]),dict(preflight_rechecks=2),dict(reason='Current price changed')):
   bad=dict(id='a',status='blocked',reason='ConnectTimeout',**{}) ;bad.update(change);self.assertFalse(retryable(bad))
if __name__=='__main__':unittest.main()
