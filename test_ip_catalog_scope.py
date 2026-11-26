import ast,pathlib,unittest
t=ast.parse(pathlib.Path(__file__).with_name('ip_scheduled_source.py').read_text(encoding='utf8'));ns={};exec(compile(ast.Module(body=[x for x in t.body if isinstance(x,ast.FunctionDef)and x.name=='active_catalog_scope'],type_ignores=[]),'scope','exec'),ns)
class Test(unittest.TestCase):
 def test_new_active_outside_old_list_included(self):
  p=[{'report':'state','start_row':0,'total':3,'rows':[{'wb_id':1,'status_id':9},{'wb_id':2,'status_id':11}]},{'report':'state','start_row':100,'total':3,'rows':[{'wb_id':3,'status_id':9}]}];scope,active,total=ns['active_catalog_scope'](p,{1,2});self.assertEqual(scope,{1,2,3});self.assertEqual(active,{1,3});self.assertEqual(total,3)
 def test_missing_page_is_not_complete(self):
  with self.assertRaises(ValueError):ns['active_catalog_scope']([{'report':'state','start_row':0,'total':2,'rows':[{'wb_id':1,'status_id':9}]}],{1})
 def test_unknown_status_does_not_become_active(self):
  scope,active,total=ns['active_catalog_scope']([{'report':'state','start_row':0,'total':2,'rows':[{'wb_id':1,'status_id':9},{'wb_id':2}]}],{1});self.assertEqual(active,{1})
 def test_no_active_does_not_claim_healthy(self):
  with self.assertRaises(ValueError):ns['active_catalog_scope']([{'report':'state','start_row':0,'total':1,'rows':[{'wb_id':1,'status_id':11}]}],{1})
if __name__=='__main__':unittest.main()

