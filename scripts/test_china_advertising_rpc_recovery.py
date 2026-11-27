import unittest
from unittest.mock import patch
from china_advertising_state import AdvertisingIO
class ReportRpcRecovery(unittest.TestCase):
 def test_520_before_commit_retries_only_report_rpc(self):
  io=AdvertisingIO.__new__(AdvertisingIO);p={'status':'complete'}
  with patch.object(io,'db',side_effect=[RuntimeError('State HTTP 520'),True])as db,patch.object(io,'get',return_value=None),patch('china_advertising_state.time.sleep'):
   self.assertTrue(io._report_write('report',p,False))
   self.assertEqual(2,db.call_count)
   self.assertTrue(all(c.args[:2]==('rpc/china_advertising_report_state_v1','POST')for c in db.call_args_list))
 def test_lost_create_ack_recovers_without_second_insert(self):
  io=AdvertisingIO.__new__(AdvertisingIO);p={'status':'complete'}
  with patch.object(io,'db',side_effect=RuntimeError('State HTTP 520'))as db,patch.object(io,'get',return_value=p):
   self.assertTrue(io._report_write('report',p,True));self.assertEqual(1,db.call_count)
 def test_wrong_existing_payload_does_not_count_as_success(self):
  io=AdvertisingIO.__new__(AdvertisingIO)
  with patch.object(io,'db',side_effect=RuntimeError('State HTTP 520'))as db,patch.object(io,'get',return_value={'other':1}),patch('china_advertising_state.time.sleep'):
   with self.assertRaisesRegex(RuntimeError,'520'):io._report_write('report',{'status':'complete'},True)
   self.assertEqual(3,db.call_count)
