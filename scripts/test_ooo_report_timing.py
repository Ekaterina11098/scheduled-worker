import ast,datetime,json,unittest
from pathlib import Path
P=Path(__file__).parent
class Timing(unittest.TestCase):
 def test_targets_unchanged(self):
  tree=ast.parse((P/'ooo_daily_reports.py').read_text(encoding='utf-8'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='send_target');ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'target','exec'),ns)
  now=datetime.datetime(2026,11,28,6,0,tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
  self.assertEqual(ns['send_target'](now,'morning').strftime('%H:%M'),'07:30');self.assertEqual(ns['send_target'](now,'midday').strftime('%H:%M'),'15:00')
 def test_warm_phase_cannot_request_fullstats_or_send(self):
  template=json.loads((P/'ooo_report_templates.json').read_text(encoding='utf-8'))['midreader']
  self.assertLess(template.index("if os.environ.get('OOO_REPORT_CONFIG_WARM_ONLY')=='1'"),template.index("rows=get('/adv/v3/fullstats'"))
  self.assertNotIn('sendPhoto',template);self.assertNotIn('requests.post',template)
 def test_unchanged_configuration_resolver_present_in_both_collectors(self):
  assets=json.loads((P/'ooo_report_templates.json').read_text(encoding='utf-8'))
  for k in('collector','midreader'):self.assertIn('resolve(db,',assets[k]);compile(assets[k],k,'exec')
 def test_waiting_preserves_sending_deadline(self):
  src=(P/'ooo_daily_reports.py').read_text(encoding='utf-8')
  self.assertIn('now.hour,now.minute)>=(6,0)',src);self.assertIn('now.hour,now.minute)>=(13,40)',src)
  self.assertIn("slot=='midday'and(now.hour,now.minute)<(14,50)",src)
  self.assertIn('if prepare_only or isinstance(error,ReportNotReady)',src)
  self.assertIn('min(now.timestamp()+delay,send_target(now,slot).timestamp())',src)
if __name__=='__main__':unittest.main()
