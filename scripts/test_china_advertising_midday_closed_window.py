import unittest
from unittest.mock import patch
from china_midday_completed_review import completed_campaign_stats
class ClosedBeforeWindow(unittest.TestCase):
 def campaign(self,status=7,deleted='2026-11-11T09:41:37+03:00'):
  return dict(id=1,status=status,timestamps=dict(created='2026-11-04T13:00:00+03:00',deleted=deleted))
 def test_terminal_archive_before_window_has_dated_empty_window_without_api(self):
  with patch('china_midday_completed_review.http',side_effect=AssertionError('No API needed')):
   row=completed_campaign_stats(None,[self.campaign()],{},'2026-11-17','2026-11-19')[1]
  self.assertEqual('closed_before_completed_window',row['history_status'])
  self.assertEqual(0,row['sum']);self.assertEqual([],row['days'])
 def test_saved_history_and_expenses_are_preserved(self):
  old=dict(advertId=1,days=[dict(date='2026-11-04',sum=25)],sum=25)
  with patch('china_midday_completed_review.http',side_effect=AssertionError('No API needed')):
   rows=completed_campaign_stats(None,[self.campaign()],{1:old},'2026-11-17','2026-11-19')
  self.assertEqual(old,rows[1])
 def test_archive_within_first_day_is_not_zero(self):
  with patch('china_midday_completed_review.http',return_value={}):
   with self.assertRaisesRegex(ValueError,'expected list'):
    completed_campaign_stats(None,[self.campaign(deleted='2026-11-17T00:01:00+03:00')],{},'2026-11-17','2026-11-19')
 def test_pause_or_undated_archive_cannot_prove_empty_history(self):
  for c in (self.campaign(status=11),self.campaign(deleted=None)):
   with self.subTest(c=c),patch('china_midday_completed_review.http',return_value={}):
    with self.assertRaisesRegex(ValueError,'expected list'):
     completed_campaign_stats(None,[c],{},'2026-11-17','2026-11-19')
if __name__=='__main__':unittest.main()
