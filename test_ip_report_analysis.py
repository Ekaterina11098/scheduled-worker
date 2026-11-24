import copy,sys,types,unittest
from unittest.mock import patch
try:import requests
except ImportError:sys.modules['requests']=types.SimpleNamespace(post=lambda *a,**kw:None)
from ip_report_analysis import financial_result,economics,screen,review_report,Halt,ROOT
from test_ip_cloud_dialog import FakeState
DAY='2026-11-05'
def fixture():
 own=[dict(p_id=1,nm_id=101,sa_name='101-Bag-black',subject_id=50,orders_count=3,orders_sum=3000,stock_api_stock_count=30,fbs_stock=0,profit=99999)]
 inp=dict(period=DAY,own=own,finance={},models={'101':{'historical_order_price':1000,'scenario_one_buyout_after_assumed_5pct_ad':200,'period_to':'2026-11-01','not_current_period_profit':True}},gaps=[])
 a=dict(nm=101,sku='101-Bag-black',campaign=1,kind='raise_bid',stored_bid_minor=295,target_bid_minor=309,daily={DAY:dict(spend=20,orders=3,revenue=3000,clicks=10,views=100)},criterion='Проверка',baseline={})
 c=dict(actions=[a],review_coverage={'own_articles':1,'existing_pairs':1})
 v=dict(period=DAY,campaigns=[dict(campaign_id=1,spend=100,budget=dict(valid=True,today_observation=True,balance=5000,observed_at='2026-11-06T04:30:00Z'),sku_rows=[])])
 return inp,c,v
class AnalysisTests(unittest.TestCase):
 def test_report_claim_stays_inside_existing_cloud_scope(self):
  from ip_report_analysis import ROOT_REPORT
  self.assertTrue(ROOT_REPORT.startswith(ROOT))
 def test_ip_tax_and_no_second_ad_deduction(self):
  v=dict(period_from=DAY,period_to=DAY,cabinet='token_2',currency='RUB',for_pay=700,seller_sales=1000,seller_returns=-200,net_units=1,own_unit_cost=100,financial_ads=50,for_pay_includes_ads=True,expenses_reconciled=True,own_cost_source='saved-own-cost')
  r=financial_result(v,DAY);self.assertEqual(r['tax_reserve'],120);self.assertEqual(r['after_ads'],480);self.assertEqual(r['before_ads'],530)
  for key,value in [('currency','CNY'),('cabinet','token_3'),('tax_reserve_rate',.05),('expenses_reconciled',False),('period_to','2026-11-04')]:
   other=dict(v,**{key:value});self.assertEqual(financial_result(other,DAY)['status'],'unknown')
 def test_unknown_is_not_zero_or_mpstats_profit(self):
  inp,_,_=fixture();r=economics(inp)['101'];self.assertIsNone(r['profit_after_ads']);self.assertIsNone(r['buyout_probability']);self.assertTrue(r['conditional_model']['not_current_period_profit'])
 def test_period_profit_not_reused_and_zero_is_known(self):
  inp,_,_=fixture();inp['finance']['101']=dict(status='preliminary',period_from=DAY,period_to='2026-11-04',after_ads=500,all_channels=True,campaign_profit=False)
  self.assertIsNone(economics(inp)['101']['profit_after_ads']);inp['finance']['101'].update(period_to=DAY,after_ads=0);self.assertEqual(economics(inp)['101']['profit_after_ads'],0)
 def test_best_growth_placement_per_sku_and_no_caps(self):
  inp,c,v=fixture();second=copy.deepcopy(c['actions'][0]);second['campaign']=2;second['daily'][DAY]['orders']=1;c['actions'].append(second);v['campaigns'].append(dict(v['campaigns'][0],campaign_id=2))
  a,audit=screen(c,v,inp);self.assertEqual(len(a),1);self.assertEqual(a[0]['campaign'],1);self.assertTrue(a[0]['growth_reserve']['not_daily_cap']);self.assertFalse(audit['rules']['msk50_required'])
 def test_no_reserve_no_ready_growth_and_no_automatic_topup(self):
  inp,c,v=fixture();v['campaigns'][0]['budget']['balance']=1;a,audit=screen(c,v,inp);self.assertEqual(a,[]);self.assertTrue(audit['research'])
 def test_fbo_only_no_fbs_future_supply(self):
  inp,c,v=fixture();inp['own'][0].update(subject_id=51,stock_api_stock_count=0,fbs_stock=1000);a,_=screen(c,v,inp);self.assertEqual(a,[])
 def test_isolated_high_ratio_is_not_persistent(self):
  inp,c,v=fixture();a=c['actions'][0];a['kind']='lower_bid';a['daily']={DAY:dict(spend=10,orders=1,revenue=100), '2026-11-04':dict(spend=1,orders=10,revenue=1000)};result,audit=screen(c,v,inp);self.assertEqual(result,[]);self.assertTrue(audit['rejected'])
 def test_marginal_economics_uses_ip_stress_cost(self):
  inp,c,v=fixture();inp['marginal_models']={'101':dict(cabinet='token_2',currency='RUB',tax_reserve_rate=.15,period_to=DAY,verified=True,expected_margin_before_ads=5,stress_margin_before_ads=5)};a,_=screen(c,v,inp);self.assertEqual(a,[])

 def test_rules_never_call_model_even_with_expired_price_or_uncertain_old_receipt(self):
  inp,c,v=fixture();state=FakeState()
  state.data[ROOT+'policy'].update(report_review_enabled=True,advertising_strategy='cost_reduction_only',price_valid_until='2000-01-01')
  state.data[ROOT+'report-analysis:v4:'+DAY]={'status':'uncertain_no_retry'}
  writes=[]
  class Store:
   def cache_set(self,*a,**kw):writes.append((a,kw))
  prior=copy.deepcopy(state.data)
  with patch('ip_report_analysis.State',return_value=state),patch('ip_report_analysis.load_inputs',return_value=inp),patch('requests.post',side_effect=AssertionError('No network/model')),patch('ip_cloud_dialog.Budget.reserve',side_effect=AssertionError('No paid reservation')):
   a=review_report(Store(),v,c);b=review_report(Store(),v,c)
  self.assertEqual(state.data,prior);self.assertEqual(a,b);self.assertEqual(a['actions'],[])
  r=a['sol_analysis'];self.assertEqual(r['status'],'rules_reviewed');self.assertEqual(r['backend'],'rules_no_model');self.assertIsNone(r['model']);self.assertEqual(r['model_calls_this_run'],0);self.assertEqual(r['charged_micro_usd'],0)
  self.assertNotIn('analysis_notice',a);self.assertTrue(all(x[0][0].startswith(ROOT+'report-rules:v1:')for x in writes))
  self.assertEqual(c['actions'][0]['kind'],'raise_bid');self.assertEqual(a['review_coverage']['directions']['raise']['ready'],0)
 def test_only_screened_reductions_keep_exact_parameters_and_current_evidence(self):
  inp,c,v=fixture();state=FakeState();state.data[ROOT+'policy'].update(report_review_enabled=True,advertising_strategy='cost_reduction_only')
  decrease=copy.deepcopy(c['actions'][0]);decrease.update(kind='lower_bid',target_bid_minor=280);c['actions'].append(decrease)
  allowed=dict(decrease,analysis_id='checked-lower',ip_economics={'profit_after_ads':None},analysis_metrics={})
  audit=dict(economics={'101':{'profit_after_ads':None}},rejected=[{'reason':'insufficient evidence'}],research=[],gaps=['finance unknown'])
  class Store:
   def cache_set(self,*a,**kw):pass
  with patch('ip_report_analysis.State',return_value=state),patch('ip_report_analysis.load_inputs',return_value=inp),patch('ip_report_analysis.screen',return_value=([allowed],audit))as screened:
   out=review_report(Store(),v,c)
   self.assertEqual([a['kind']for a in screened.call_args.args[0]['actions']],['lower_bid'])
   self.assertEqual(out['actions'],[allowed]);self.assertEqual(out['actions'][0]['target_bid_minor'],280);self.assertTrue(out['historical_profit_only']);self.assertEqual(out['ip_economic_review']['gaps'],['finance unknown'])
   screened.return_value=([],audit);out2=review_report(Store(),v,c)
   self.assertEqual(out2['actions'],[]);self.assertNotEqual(out['plan_sha256'],out2['plan_sha256'])
 def test_disabled_or_unapproved_strategy_fails_closed_before_reading_sources(self):
  inp,c,v=fixture();state=FakeState()
  with patch('ip_report_analysis.State',return_value=state),patch('ip_report_analysis.load_inputs',side_effect=AssertionError('no read')):
   with self.assertRaises(Halt):review_report(None,v,c)
   state.data[ROOT+'policy'].update(report_review_enabled=True,advertising_strategy='unapproved_growth')
   with self.assertRaises(Halt):review_report(None,v,c)
if __name__=='__main__':unittest.main()
