import unittest
from ooo_daily_review import evaluate_funding
class FundingChecks(unittest.TestCase):
 def check(self,status=11,cid=39605581,missing=None,balance=0,clicks=100,spend=300,economy=100):
  rows=[{'members':[{'cid':cid}],'free_msk':10,'stock_wb':{'wb':10},'model_lower_before_ads_rub':economy}]
  c={'day':{'sum':100,'sum_price':10000},'three':{'sum':spend,'sum_price':30000,'clicks':clicks}}
  return evaluate_funding(str(cid),{'status':status},c,balance,rows,missing or[])
 def test_paused_can_propose(self):
  r=self.check();self.assertEqual(r['decision'],'propose_topup');self.assertEqual(r['amount_kgs'],1200);self.assertFalse(r['resume_authorized'])
 def test_active_unchanged(self):self.assertEqual(self.check(status=9)['decision'],'propose_topup')
 def test_owner_hold_preserved(self):self.assertEqual(self.check(cid=41517533)['decision'],'owner_hold')
 def test_missing_days_not_zero(self):self.assertEqual(self.check(missing=['2026-11-15'])['decision'],'incomplete_recent_days')
 def test_late_attribution_not_funding(self):self.assertEqual(self.check(clicks=3,spend=9.65)['decision'],'paused_recent_delivery_insufficient')
 def test_enough_budget(self):self.assertEqual(self.check(balance=150)['decision'],'budget_sufficient')
 def test_bad_economy_blocks(self):self.assertEqual(self.check(economy=-1)['decision'],'economics_or_stock_unconfirmed')
 def test_high_drr_blocks(self):self.assertEqual(self.check(spend=2000)['decision'],'drr_above_target')
if __name__=='__main__':unittest.main()


