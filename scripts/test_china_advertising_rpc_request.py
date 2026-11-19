import ast,json,types,unittest
from pathlib import Path

class RpcRequestTests(unittest.TestCase):
 def call(self,path):
  tree=ast.parse(Path(__file__).with_name('china_price_apply.py').read_text(encoding='utf-8'))
  cl=next(x for x in tree.body if isinstance(x,ast.ClassDef)and x.name=='IO');method=next(x for x in cl.body if isinstance(x,ast.FunctionDef)and x.name=='db')
  calls=[]
  class Response:
   ok=True;content=b'true'
   def json(self):return True
  def request(*a,**kw):calls.append(kw);return Response()
  ns=dict(json=json,requests=types.SimpleNamespace(request=request));exec(compile(ast.Module(body=[method],type_ignores=[]),'production-db','exec'),ns)
  io=types.SimpleNamespace(url='https://example.invalid',headers={},state_cache_compact_utf8=True,state_cache_read_timeout=90)
  ns['db'](io,path,'POST',{'text':'Проверка'})
  return calls[0]
 def test_report_rpc_compact_utf8_and90second_timeout(self):
  c=self.call('rpc/china_advertising_report_state_v1');self.assertEqual(c['timeout'],(10,90));self.assertEqual(json.loads(c['data']),{'text':'Проверка'});self.assertNotIn(b'\\u',c['data'])
 def test_marketplace_unrelated_path_keeps_original_options(self):
  c=self.call('other_path');self.assertEqual(c['timeout'],30);self.assertEqual(c['json'],{'text':'Проверка'});self.assertNotIn('data',c)
if __name__=='__main__':unittest.main()

