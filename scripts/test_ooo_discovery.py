import ast,json,sys,types,unittest
from pathlib import Path
sys.modules.setdefault('china_codex_cloud',types.SimpleNamespace(DB=object,stamp=lambda:None))
import ooo_daily_reports as report
T=json.loads(Path(__file__).with_name('ooo_report_templates.json').read_text())

class Discovery(unittest.TestCase):
 def config_fn(self):
  tree=ast.parse(T['collector']);run=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='run')
  return next(n for n in ast.walk(run)if isinstance(n,ast.FunctionDef)and n.name=='configurations')
 def test_new_campaign_configuration_requested(self):
  ids=[1];calls=[]
  def raw(host,path,params=None):
   got=list(map(int,params['ids'].split(',')));calls.extend(got)
   return {'adverts':[{'id':cid,'currency':'KGS'}for cid in got]}
  ns={'IDS':ids,'state':{'sources':{'campaign_list':{'data':{'adverts':[{'status':9,'advert_list':[{'advertId':2}]}]}}}},'raw':raw}
  exec(compile(ast.Module(body=[self.config_fn()],type_ignores=[]),'test','exec'),ns)
  self.assertEqual(set(ns['configurations']()),{'1','2'});self.assertEqual(calls,[1,2])
 def test_new_campaign_cannot_be_silently_omitted(self):
  with self.assertRaises(report.ReportNotReady):report.require_complete_statistics([],['2026-11-23'],{'2':{'status':9}})
 def test_precreation_days_do_not_require_fake_zeros(self):
  cfg={'2':{'status':9,'timestamps':{'created':'2026-11-23T10:00:00+03:00'}}}
  rows=[{'advertId':2,'currency':'KGS','days':[{'date':'2026-11-23','sum':585,'sum_price':4577,'orders':1,'clicks':180,'views':6016}]}]
  self.assertEqual(report.require_complete_statistics(rows,['2026-11-21','2026-11-22','2026-11-23'],cfg)['campaign_ids'],[2])
 def test_archived_omission_does_not_block(self):
  report.require_complete_statistics([],['2026-11-23'],{'1':{'status':7}})
 def test_renderers_compile_and_discover_unknown_names(self):
  for key,var in [('renderer','a'),('midrenderer','analysis')]:
   compile(T[key],key,'exec')
   tree=ast.parse(T[key]);nodes=[]
   for n in tree.body:
    if isinstance(n,ast.Assign)and any(isinstance(x,ast.Name)and x.id=='names'for x in n.targets):nodes.append(n)
    elif isinstance(n,ast.Expr)and isinstance(n.value,ast.Call)and ast.unparse(n.value.func)=='names.update':nodes.append(n)
   ns={var:{'configurations':{'42139012':{'status':9,'settings':{'name':'New campaign'}}}}}
   exec(compile(ast.Module(body=nodes,type_ignores=[]),'names','exec'),ns)
   self.assertEqual(ns['names'][42139012],'New campaign')
 def test_every_template_compiles(self):
  for key,value in T.items():compile(value,key,'exec')

if __name__=='__main__':unittest.main()
