import copy,importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch

class LargeReportStateTests(unittest.TestCase):
 def setUp(self):
  stub=types.ModuleType('china_price_apply')
  class Base:
   def create(self,k,p):self.rows[k]=copy.deepcopy(p);self.calls.append(('ordinary_create',k));return True
  stub.IO=Base
  with patch.dict(sys.modules,{'china_price_apply':stub,'requests':types.ModuleType('requests')}):
   spec=importlib.util.spec_from_file_location('report_transport_fixture',Path(__file__).with_name('china_advertising_state.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  class Transport(module.AdvertisingIO):
   def __init__(self):self.rows={};self.calls=[]
   def get(self,k):return copy.deepcopy(self.rows.get(k))
   def db(self,path,method='GET',body=None,prefer=None):
    self.calls.append((path,method))
    if path.startswith('rpc/'):
     k=body['p_key']
     if body['p_create']and k in self.rows:return False
     if not body['p_create']and k not in self.rows:return False
     self.rows[k]=copy.deepcopy(body['p_payload']);return True
    key=path.split('eq.')[1]
    from urllib.parse import unquote
    self.rows[unquote(key)]=copy.deepcopy(body['payload']);return []
  self.io=Transport();self.key='china_agent:advertising_source:2026-11-19:v2';self.big={'kept':'x'*1000001}
 def test_large_report_roundtrip_keeps_all_data(self):
  self.assertTrue(self.io.create(self.key,self.big));self.assertEqual(self.io.get(self.key),self.big)
  self.io.put(self.key,dict(self.big,flag=True));self.assertEqual(self.io.get(self.key),dict(self.big,flag=True))
  self.assertTrue(all(c[0]=='rpc/china_advertising_report_state_v1'for c in self.io.calls))
 def test_existing_create_remains_false_without_overwrite(self):
  self.io.create(self.key,self.big);self.assertFalse(self.io.create(self.key,dict(self.big,new=True)));self.assertEqual(self.io.get(self.key),self.big)
 def test_missing_put_does_not_invent_row(self):
  with self.assertRaisesRegex(RuntimeError,'row missing'):self.io.put(self.key,self.big)
  self.assertIsNone(self.io.get(self.key))
 def test_memory_and_execution_never_use_report_rpc(self):
  for key in ('china_agent:shared_memory:v1:work:note:fixture','china_agent:owner_example:execution'):
   self.assertFalse(self.io._large_report(key,self.big))
 def test_small_report_keeps_existing_transport(self):
  self.io.put(self.key,{'small':True});self.assertTrue(self.io.calls[0][0].startswith('telegram_api_cache?'))
if __name__=='__main__':unittest.main()

