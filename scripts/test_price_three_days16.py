import unittest
from datetime import date
from china_price_experiment_result import experiment_result
from china_daily_expected_control import comparison_windows
class ThreeDayPriceReview(unittest.TestCase):
 def test_boundary(self):
  self.assertNotEqual(experiment_result(100,90,100,5,100,5,2,20)['status'],'rollback_review')
  self.assertEqual(experiment_result(100,90,100,5,100,5,3,20)['status'],'rollback_review')
 def test_change_day_excluded(self):
  self.assertEqual(comparison_windows(date(2026,11,12),date(2026,11,16))[1],(date(2026,11,13),date(2026,11,15)))
  self.assertIsNone(comparison_windows(date(2026,11,16),date(2026,11,17)))
 def test_profit_decline_without_cr_decline(self):
  self.assertEqual(experiment_result(100,80,100,5,100,6,3,20)['status'],'rollback_review')
if __name__=='__main__':unittest.main()
