import unittest
from china_archived_report_window import outside_window_without_statistics as outside
class ArchiveWindow(unittest.TestCase):
 def cp(self,deleted='2026-11-11T09:41:37+03:00',status=7):
  return dict(status=status,timestamps=dict(deleted=deleted))
 def test_verified_archive_before_window_without_statistics(self):
  self.assertTrue(outside(self.cp(),None,'2026-11-17'))
 def test_reported_statistics_are_never_discarded(self):
  self.assertFalse(outside(self.cp(),dict(spend=12),'2026-11-17'))
 def test_archive_inside_window_still_needs_statistics(self):
  self.assertFalse(outside(self.cp('2026-11-17T01:00:00+03:00'),None,'2026-11-17'))
 def test_deletion_date_is_moscow_not_utc(self):
  self.assertFalse(outside(self.cp('2026-11-16T22:00:00Z'),None,'2026-11-17'))
 def test_current_or_unverified_archive_still_needs_statistics(self):
  for c in (self.cp(status=9),self.cp(None),self.cp('2026-11-11T09:00:00'),self.cp('bad')):
   self.assertFalse(outside(c,None,'2026-11-17'))
if __name__=='__main__':unittest.main()
