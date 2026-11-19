import ast,copy,types,sys,unittest
from pathlib import Path
from unittest.mock import patch

class OwnerViewValidationTests(unittest.TestCase):
 def setUp(self):
  tree=ast.parse(Path(__file__).with_name('china_advertising_v2_png.py').read_text(encoding='utf-8'));nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('render','owner_launch_day_view','validate_mandatory_format')]
  self.rendered=[]
  def render(b):self.rendered.append(copy.deepcopy(b));return [dict(family='drr'),dict(family='budgets')]
  ns={'_render_legacy':render};exec(compile(ast.Module(body=nodes,type_ignores=[]),'production-render','exec'),ns);self.render=ns['render']
  directions=types.ModuleType('china_advertising_directions');directions.campaign_table=lambda b:b;self.p=patch.dict(sys.modules,{'china_advertising_directions':directions});self.p.start();self.addCleanup(self.p.stop)
  metric=dict(spend=1,amount=100,orders=1,clicks=10)
  self.bundle=dict(day='2026-11-19',days=['2026-11-16','2026-11-17','2026-11-18'],mandatory_campaign_format=True,recommendation_directions={k:[]for k in('raise','add','reduce','exclude')},campaigns=[dict(id=1,name='existing',status=9,period=metric,last=metric),dict(id=42022679,name='new today',status=9,period=None,last=None)])
 def test_owner_excluded_launch_does_not_block_both_reports(self):
  before=copy.deepcopy(self.bundle);files=self.render(self.bundle);self.assertEqual([f['family']for f in files],['drr','budgets']);self.assertEqual([c['id']for c in self.rendered[0]['campaigns']],[1]);self.assertEqual(self.bundle,before)
 def test_other_missing_campaign_still_blocks(self):
  self.bundle['campaigns'][0]['period']=None
  with self.assertRaisesRegex(ValueError,'Complete campaign statistics'):self.render(self.bundle)
 def test_next_day_never_reuses_owner_launch_day_exclusion(self):
  self.bundle.update(day='2026-11-20',days=['2026-11-17','2026-11-18','2026-11-19'])
  with self.assertRaisesRegex(ValueError,'42022679'):self.render(self.bundle)
if __name__=='__main__':unittest.main()

