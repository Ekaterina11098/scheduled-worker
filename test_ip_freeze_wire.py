import ast,base64,hashlib,json,os,pathlib,sys,types,unittest,datetime
P=pathlib.Path(__file__).parent
ns=dict(base64=base64,hashlib=hashlib,json=json,os=os,ROOT='advertising:ip:report_clock:v1:',CHAT=-1004378639510,BOT=8987327588,datetime=datetime.datetime,timezone=datetime.timezone)
tree=ast.parse((P/'ip_report_freeze.py').read_text(encoding='utf8'))
for n in tree.body:
 if isinstance(n,ast.FunctionDef)and n.name in('json_native','wake_prepared'):exec(compile(ast.Module(body=[n],type_ignores=[]),'freeze','exec'),ns)
class Tests(unittest.TestCase):
 def setUp(self):
  self.calls=[];self.saved=[];self.delivery={};ns['store']=types.SimpleNamespace(cache_get=lambda k:self.delivery,cache_set=lambda *a,**kw:self.saved.append(a));self.old=sys.modules.get('requests');sys.modules['requests']=types.SimpleNamespace(post=lambda *a,**kw:self.calls.append((a,kw))or types.SimpleNamespace(status_code=200));os.environ['SUPABASE_SECRET_KEY']='unit-test-key';os.environ['SUPABASE_URL']='https://example.invalid'
  raw=b'unit-test-media';self.artifact=dict(status='ready',day='2026-11-27',slot='midday',chat_id=ns['CHAT'],bot_id=ns['BOT'],images=[dict(data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())])
 def tearDown(self):
  if self.old is None:sys.modules.pop('requests',None)
  else:sys.modules['requests']=self.old
 def test_real_budget_coverage_tuple_roundtrip(self):
  value={'budget_coverage':{'known':9,'active':9,'omitted':[(41519741,'нулевой расход; срок не рассчитывается')],'proposals':1},'images':self.artifact['images']}
  wire=ns['json_native'](value);self.assertEqual(wire,json.loads(json.dumps(value)));self.assertEqual(wire['images'],value['images']);self.assertNotEqual(wire,value)
 def test_late_ready_wakes_existing_clock(self):
  ns['wake_prepared']('2026-11-27','midday',self.artifact);self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0][0][0],'https://example.invalid/functions/v1/ip-report-clock');self.assertTrue(self.saved)
 def test_confirmed_delivery_is_not_requested_again(self):
  self.delivery={'status':'complete'};ns['wake_prepared']('2026-11-27','midday',self.artifact);self.assertEqual(self.calls,[])
 def test_bad_hash_or_scope_does_not_publish(self):
  self.artifact['images'][0]['sha256']='wrong'
  with self.assertRaises(RuntimeError):ns['wake_prepared']('2026-11-27','midday',self.artifact)
  self.assertEqual(self.calls,[])
if __name__=='__main__':unittest.main()
