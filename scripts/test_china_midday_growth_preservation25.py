import copy,unittest
from unittest.mock import patch
import china_advertising_decision_contract as contract
from china_advertising_target import resolve
from china_archived_report_window import midday_view
from china_advertising_midday import recommendations
class GrowthPreservation(unittest.TestCase):
 def setUp(self):
  self.action=dict(id='1:10',kind='ad_set_bid',direction='raise',campaign_id=1,nm_id=10,placement='search',old_minor=28,target_minor=30,growth_evidence=dict(cabinet='token_3',currency='CNY',source_key='verified-source',price_cny=200,decision_days=['2026-11-24']))
  self.row=dict(nm=10,article='test',decision='Тест: повысить 0.28 → 0.30 CNY.',action=self.action,decision_window=dict(days=['2026-11-24'],metrics=dict(clicks=200,orders=4,amount=1000,spend=56)),pending_first_day=False)
  self.bundle=dict(day='2026-11-25',days=['2026-11-24'],target_drr_pct=8,campaigns=[dict(id=1,status=9,focus=[self.row],attention=[self.row])])
  self.source=dict(period_to='2026-11-24',config=dict(cpcMaxBid=1000,cpcStep=1),executions=[],batches={'x':dict(campaigns={'adverts':[dict(id=1,status=9,currency='CNY',nm_settings=[dict(nm_id=10,bids_kopecks={'search':28})])]})},economics={'rows':{'10':dict(stock_free=10,published_stock=5,seller_price_cny=200,expected_margin_before_ads_cny=40)}})
  self.minima={'1:10':28}
 def run_final(self,change=None):
  def economic(b,s,m):
   b=copy.deepcopy(b);b['campaigns'][0]['focus'][0]['action']=None
   if change:change(b['campaigns'][0]['focus'][0])
   return b
  with patch('china_advertising_economic_review.apply',economic),patch('china_advertising_directions.attach',lambda b,s:b):return contract.finalize(None,self.bundle,self.source,self.minima)
 def test_ready_raise_survives_second_economic_pass(self):
  self.assertEqual(self.run_final()['campaigns'][0]['attention'][0]['action'],self.action)
 def test_pending_day_does_not_restore_raise(self):
  self.assertFalse(self.run_final(lambda r:r.update(pending_first_day=True))['campaigns'][0]['attention'])
 def test_changed_bid_is_not_replayed(self):
  self.source['batches']['x']['campaigns']['adverts'][0]['nm_settings'][0]['bids_kopecks']['search']=30
  self.assertFalse(self.run_final()['campaigns'][0]['attention'])
 def test_exact_minimum_required(self):
  self.minima={};self.assertFalse(self.run_final()['campaigns'][0]['attention'])
 def test_owner_eight_percent_is_enforced(self):
  self.action['target_minor']=50;self.assertFalse(self.run_final()['campaigns'][0]['attention'])
 def test_changed_price_not_restored(self):
  self.source['economics']['rows']['10']['seller_price_cny']=201;self.assertFalse(self.run_final()['campaigns'][0]['attention'])
 def test_no_stock_not_restored(self):
  self.source['economics']['rows']['10']['published_stock']=0;self.assertFalse(self.run_final()['campaigns'][0]['attention'])
 def test_real_cost_action_takes_precedence(self):
  a=dict(kind='ad_exclude_sku',nm_id=10,campaign_id=1)
  self.assertEqual(self.run_final(lambda r:r.update(action=a))['campaigns'][0]['attention'][0]['action'],a)
 def test_protected_campaign_stays_unchanged(self):
  self.bundle['campaigns'][0]['id']=42088552;self.action['campaign_id']=42088552;self.source['batches']['x']['campaigns']['adverts'][0]['id']=42088552;self.minima={'42088552:10':28}
  self.assertFalse(self.run_final()['campaigns'][0]['attention'])
 def test_wait_and_missing_and_protected_are_explicit(self):
  self.assertEqual(recommendations(dict(today={},attention=[],post_change_note='Оценка27.11.')),['Без изменений.'])
  self.assertEqual(recommendations(dict(today=None,attention=[])),['Без изменений.']);self.assertEqual(recommendations(dict(owner_unchanged=True,attention=[])),['Ничего не менять.'])
 def test_diagnostics_and_unready_candidates_remain_private(self):
  row=dict(attention=[],addition_review_notes=['Кандидат, нужен план.'],recommendation_review_note='Нет полной истории.',owner_review_note='Ожидание.',post_change_note='Тест не завершён.')
  self.assertEqual(recommendations(row),['Без изменений.'])
 def test_unready_additions_are_not_counted_as_ready(self):
  from china_advertising_midday import direction_count
  self.assertEqual(direction_count(dict(status='checked',count=2,ready_count=0,unready_count=2),'add'),'0 (проверяются: 2)')
 def test_same_day_zero_archive_is_omitted(self):
  b=dict(day='2026-11-25',campaigns=[dict(id=1,status=9,today=dict(spend=1)),dict(id=2,status=7,archived_at='2026-11-25T12:00:00+03:00',today=dict(spend=0,orders=0,clicks=0,amount=0))]);v=midday_view(b);self.assertEqual([c['id']for c in v['campaigns']],[1]);self.assertEqual(len(v['presentation_totals_campaigns']),2)
 def test_archived_spend_is_not_lost(self):
  b=dict(day='2026-11-25',campaigns=[dict(id=2,status=7,today=dict(spend=12,orders=0,clicks=2,amount=0))]);self.assertEqual(midday_view(b)['campaigns'],b['campaigns'])
 def test_dated_owner_target(self):
  class IO:
   def get(self,k):return dict(status='active',cabinet='token_3',source_ref='owner25',effective_from='2026-11-25',target_drr_pct=8)
  self.assertEqual(resolve(IO(),dict(day='2026-11-25'),{}),8);self.assertEqual(resolve(IO(),dict(day='2026-11-24'),{}),5)
 def test_verified_bulk_price_is_retained_by_compaction(self):
  from china_advertising_v2 import history,compact_execution_records
  item=dict(nmID=10,article='test',status='applied',old_cny='200',target_cny='230',request=dict(nmID=10,price=460,discount=50),readback=dict(nmID=10,currencyIsoCode4217='CNY',discount=50,sizes=[dict(price=460,discountedPrice=230)]))
  record=dict(status='done',completed_at='2026-11-24T14:57:14+00:00',items=[item]);events=history(compact_execution_records([record]));self.assertEqual([(e['nm'],e['kind'])for e in events],[(10,'price')])
 def test_unverified_bulk_price_does_not_create_event(self):
  from china_advertising_v2 import history,compact_execution_records
  item=dict(nmID=10,status='applied',old_cny='200',target_cny='230',request=dict(nmID=10,price=460,discount=50),readback=dict(nmID=10,currencyIsoCode4217='CNY',discount=50,sizes=[dict(price=460,discountedPrice=229)]))
  self.assertFalse(history(compact_execution_records([dict(status='done',completed_at='2026-11-24T14:57:14+00:00',items=[item])])) )
if __name__=='__main__':unittest.main()
