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

class ArchiveReportView(unittest.TestCase):
 def test_budget_inventory_restore_does_not_restore_published_row(self):
  from china_archived_report_window import report_view
  old=dict(id=41570073,status=7,period=None,last=None,budget_inventory_state=dict(id=41570073,status=7,timestamps=dict(deleted='2026-11-11T09:41:37+03:00')))
  live=dict(id=40933588,status=9,period=dict(spend=100),last=dict(spend=30))
  bundle=dict(days=['2026-11-17','2026-11-18','2026-11-19'],campaigns=[old,live],budget_audit={'41570073':{'status':'archived'}})
  view=report_view(bundle)
  self.assertEqual([r['id']for r in view['campaigns']],[40933588])
  self.assertEqual(len(bundle['campaigns']),2)
  self.assertEqual(view['budget_audit'],bundle['budget_audit'])
  self.assertEqual(view['presentation_omitted_archives'][0]['campaign_id'],41570073)
 def test_missing_active_or_inperiod_archives_still_fail_publication(self):
  from china_archived_report_window import report_view
  rows=[dict(id=1,status=9,period=None,last=None),dict(id=2,status=7,period=None,last=None,budget_inventory_state=dict(id=2,status=7,timestamps=dict(deleted='2026-11-18T10:00:00+03:00')))]
  bundle=dict(days=['2026-11-17','2026-11-18','2026-11-19'],campaigns=rows)
  self.assertIs(report_view(bundle),bundle)
if __name__=='__main__':unittest.main()

