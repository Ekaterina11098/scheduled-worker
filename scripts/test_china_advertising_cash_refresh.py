import unittest,copy
from datetime import datetime,timezone
from china_report_cash_refresh import refresh
class CashRefresh(unittest.TestCase):
 def source(self):return dict(budget_balance_observed_at_iso='2026-11-20T04:00:48+00:00',batches={'0':dict(campaigns=dict(adverts=[dict(id=1,status=9)]),budgets=dict(adverts=[dict(advertId=1,total=1428)]))})
 def test_stale_source_reads_current_state_and_bulk_cash(self):
  calls=[]
  def http(io,path,method='GET',body=None):
   calls.append((path,method,body))
   return dict(adverts=[dict(id=1,status=9)]) if method=='GET' else dict(adverts=[dict(advertId=1,total=1200)])
  source=self.source();out=refresh(None,source,http,datetime(2026,11,20,5,42,tzinfo=timezone.utc))
  self.assertEqual(len(calls),2)
  self.assertEqual(out['batches']['0']['budgets']['adverts'][0]['total'],1200)
  self.assertEqual(source['batches']['0']['budgets']['adverts'][0]['total'],1428)
  self.assertTrue(out['budget_balance_observed_at_iso'].startswith('2026-11-20T05:42'))
 def test_recent_source_makes_no_additional_requests(self):
  source=self.source()
  self.assertIs(refresh(None,source,lambda *a: self.fail('unneeded read'),datetime(2026,11,20,4,10,tzinfo=timezone.utc)),source)
 def test_incomplete_cash_does_not_fake_freshness(self):
  source=self.source();before=copy.deepcopy(source)
  def http(io,path,method='GET',body=None):return dict(adverts=[dict(id=1,status=9)])if method=='GET'else dict(adverts=[])
  with self.assertRaises(ValueError):refresh(None,source,http,datetime(2026,11,20,6,tzinfo=timezone.utc))
  self.assertEqual(source,before)
class PublicationReadiness(unittest.TestCase):
 def test_live_missing_cash_cannot_be_published_as_finished(self):
  from china_report_cash_refresh import require_complete_cash_calculation
  with self.assertRaises(ValueError):require_complete_cash_calculation(dict(mandatory_campaign_format=True,campaigns=[dict(id=1,status=9,budget_audit_state='data_blocked')]))
 def test_economic_no_fund_and_covered_are_complete_decisions(self):
  from china_report_cash_refresh import require_complete_cash_calculation
  require_complete_cash_calculation(dict(mandatory_campaign_format=True,campaigns=[dict(id=1,status=9,budget_audit_state='covered'),dict(id=2,status=9,budget_audit_state='reviewed_no_fund')]))
if __name__=='__main__':unittest.main()

