import types,unittest,sys
from unittest.mock import patch
from china_advertising_v2 import http
class Throttle(unittest.TestCase):
 def test_read_429_respects_retry_and_keeps_exact_scope(self):
  calls=[];sleeps=[]
  class R:
   def __init__(self,n):self.ok=n==200;self.status_code=n;self.headers={'Retry-After':'75'};self.content=b'yes'
   def json(self):return {'verified':'read'}
  def req(method,url,**kw):
   calls.append((method,url,kw.get('json')));return R(429 if len(calls)==1 else 200)
  with patch.dict(sys.modules,{'requests':types.SimpleNamespace(request=req,Timeout=TimeoutError,ConnectionError=ConnectionError)}),patch('time.sleep',sleeps.append):
   self.assertEqual(http(types.SimpleNamespace(token='test'),'/adv/v3/fullstats?ids=1&beginDate=2026-11-18&endDate=2026-11-18'),{'verified':'read'})
  self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1]);self.assertEqual(sleeps,[1.5,75.0])
 def test_write_remains_forbidden(self):
  with self.assertRaises(ValueError):http(types.SimpleNamespace(token='test'),'/adv/v1/budget/deposit?id=1','POST',{'sum':100})
if __name__=='__main__':unittest.main()
