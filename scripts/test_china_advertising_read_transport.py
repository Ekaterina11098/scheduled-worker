"""Only read-only advertising requests may retry a transient network failure."""
import unittest,types
try:import requests
except ImportError:
 import sys
 requests=types.ModuleType('requests')
 class Timeout(Exception):pass
 class ConnectionError(Exception):pass
 requests.Timeout=Timeout;requests.ConnectTimeout=Timeout;requests.ConnectionError=ConnectionError
 requests.request=lambda *a,**k:None
 sys.modules['requests']=requests

from unittest.mock import patch
from china_advertising_v2 import http
class Tests(unittest.TestCase):
 def test_minimum_post_is_a_read_and_can_retry(self):
  import requests
  good=types.SimpleNamespace(ok=True,status_code=200,content=b'{}',json=lambda:{'bids':[]})
  with patch('requests.request',side_effect=[requests.ConnectTimeout('offline'),good])as call,patch('china_advertising_v2.time.sleep'):
   self.assertEqual(http(types.SimpleNamespace(token='test'),'/api/advert/v1/bids/min','POST',{}),{'bids':[]})
   self.assertEqual(call.call_count,2);self.assertEqual(call.call_args.kwargs['timeout'],(10,60))
 def test_write_rejected_without_transport(self):
  with patch('requests.request')as call:
   with self.assertRaises(ValueError):http(None,'/adv/v1/budget/deposit?id=1','POST',{})
   call.assert_not_called()
 def test_permanent_400_is_not_retried(self):
  bad=types.SimpleNamespace(ok=False,status_code=400)
  with patch('requests.request',return_value=bad)as call,patch('china_advertising_v2.time.sleep'):
   with self.assertRaises(RuntimeError):http(types.SimpleNamespace(token='test'),'/api/advert/v1/bids/min','POST',{})
   self.assertEqual(call.call_count,1)
 def test_no_unbounded_retries(self):
  import requests
  with patch('requests.request',side_effect=requests.ConnectTimeout('offline'))as call,patch('china_advertising_v2.time.sleep'):
   with self.assertRaises(requests.Timeout):http(types.SimpleNamespace(token='test'),'/adv/v1/promotion/count')
   self.assertEqual(call.call_count,2)
if __name__=='__main__':unittest.main()
