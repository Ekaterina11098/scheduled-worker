import unittest,ast,copy,json
from pathlib import Path
from ooo_composition_review import observe,signature,funding_assessment
from ooo_daily_review import evaluate_funding
def cfg(ids,status=11):return {'status':status,'currency':'KGS','bid_type':'manual','settings':{'name':'fixture','placements':{'search':False,'recommendations':True}},'nm_settings':[{'nm_id':nm,'bids_kopecks':{'search':0,'recommendations':325}}for nm in ids]}
class Composition(unittest.TestCase):
 def fixture(self):
  rows=[{'members':[{'cid':2}],'free_msk':10,'stock_wb':{'wb':10},'model_lower_before_ads_rub':100}]
  dirty={'day':{'sum':900,'sum_price':1000},'three':{'sum':900,'sum_price':1000,'clicks':300}}
  def day(dt,spend,amount):return {'date':dt,'sum':spend,'sum_price':amount,'clicks':40,'orders':2,'views':400,'apps':[{'nms':[{'nmId':1,'sum':spend,'sum_price':amount,'clicks':40,'orders':2,'views':400}]}]}
  e={'sources':{'advertising14':{'data':[{'advertId':2,'days':[day('2026-11-25',900,1000),day('2026-11-27',100,10000)]}]}}}
  return rows,dirty,e
 def test_pause_and_reordering_do_not_reset_composition(self):
  old=observe(None,cfg([1,2],9),'2026-11-25T04:00:00+00:00');new=observe(old,cfg([2,1],11),'2026-11-26T12:00:00+00:00')
  self.assertIsNone(new['changed_observed_at']);self.assertEqual(new['first_seen_at'],old['first_seen_at'])
 def test_cleanup_records_exact_removed_members(self):
  old=observe(None,cfg([1,2]),'2026-11-25T04:00:00+00:00');new=observe(old,cfg([1]),'2026-11-26T12:00:00+00:00')
  self.assertEqual(new['removed'],[2]);self.assertEqual(new['added'],[])
 def test_old_bad_native_drr_does_not_block_verified_new_composition(self):
  rows,dirty,e=self.fixture();state={'changed_observed_at':'2026-11-26T12:00:00+00:00','removed':[2]}
  result=funding_assessment(evaluate_funding,'2',cfg([1]),dirty,0,rows,[],e,'2026-11-28',state)
  self.assertEqual(result['decision'],'propose_topup');self.assertEqual(result['amount_kgs'],1200);self.assertEqual(result['day_drr'],1);self.assertFalse(result['resume_authorized'])
 def test_projected_subset_never_substitutes_for_actual_post_cleanup(self):
  rows,dirty,e=self.fixture();state={'changed_observed_at':'2026-11-26T12:00:00+00:00','removed':[2]}
  result=funding_assessment(evaluate_funding,'2',cfg([1]),dirty,0,rows,[],e,'2026-11-27',state)
  self.assertEqual(result['decision'],'awaiting_post_cleanup_statistics');self.assertIsNone(result['amount_kgs'])
 def test_bad_new_composition_still_blocks_funding(self):
  rows,dirty,e=self.fixture();e['sources']['advertising14']['data'][0]['days'][-1]['sum_price']=500
  state={'changed_observed_at':'2026-11-26T12:00:00+00:00','removed':[2]}
  self.assertEqual(funding_assessment(evaluate_funding,'2',cfg([1]),dirty,0,rows,[],e,'2026-11-28',state)['decision'],'drr_above_target')
 def test_owner_hold_survives_composition_change(self):
  rows,dirty,e=self.fixture();state={'changed_observed_at':'2026-11-26T12:00:00+00:00'}
  self.assertEqual(funding_assessment(evaluate_funding,'41517533',cfg([1]),dirty,0,rows,[],e,'2026-11-27',state)['decision'],'owner_hold')
 def test_budget_display_uses_new_metrics_without_rewriting_advertising_history(self):
  t=json.loads(Path(__file__).with_name('ooo_report_templates.json').read_text());tree=ast.parse(t['renderer'])
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='budget_column_after_cleanup')
  post={'day':{'sum':100},'three':{'sum':100}}
  ns={'z':{'internal_analysis':{'funding_checks':[{'cid':2,'post_cleanup_metrics':post,'post_cleanup_full_days':1}]}},'copy':copy,'native':lambda m:{'spend':m['sum']},'original_budget_column':lambda c:c}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'test','exec'),ns)
  old={'id':2,'last':{'spend':900},'period':{'spend':900},'balance':0}
  view=ns['budget_column_after_cleanup'](old)
  self.assertEqual(view['last']['spend'],100);self.assertEqual(view['budget_average_daily'],100);self.assertEqual(old['last']['spend'],900)
if __name__=='__main__':unittest.main()
