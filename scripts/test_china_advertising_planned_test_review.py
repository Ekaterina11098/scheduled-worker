"""Approved planned buyout is a prior, not an exemption from completed-day loss review."""
import copy,unittest
from test_china_advertising_first_full_day_pipeline import fixture,metrics
from china_advertising_economic_review import apply
from china_new_campaign_reporting import attach
class PlannedReview(unittest.TestCase):
 def run_case(self,spend=5,clicks=40,approved=True):
  b,s,cp,ds,event,m=fixture(bid=28,post=metrics(spend,clicks=clicks))
  e=s['economics']['rows']['10'];e.update(sample_size=0,buyout_fallback=True,commission_policy_fallback=True,buyout=.3,expected_margin_before_ads_cny=12)
  if approved:e['planned_buyout_source']='approved-test-plan'
  return apply(b,s,m)['campaigns'][0]['focus']
 def test_first_full_day_at_target_cost_can_exclude(self):
  r=self.run_case()[0];self.assertEqual(r['action']['kind'],'ad_exclude_sku')
  self.assertEqual(r['comparison']['to_days'],['2026-11-14'])
 def test_small_sample_not_cut(self):self.assertTrue(all(not r.get('action')for r in self.run_case(2,6)))
 def test_unapproved_fallback_not_used(self):self.assertTrue(all(not r.get('action')for r in self.run_case(5,40,False)))
 def test_verified_new_campaign_without_stats_is_visible(self):
  class IO:
   def get(self,k):
    if k=='china_agent:morning_new_campaign_reporting:v1':return dict(enabled=True,owner_id=5122667182,cabinet='token_3',campaign_ids=[])
    if k=='china_agent:verified_campaign_state:v1':return {'1':'receipt'}
    if k=='receipt':return dict(status='verified',after=dict(id=1,status=9,timestamps=dict(started='2026-11-14T12:00:00+03:00')))
    return {}
  b=dict(days=['2026-11-12','2026-11-13','2026-11-14'],campaigns=[dict(id=1,status=9,created='2026-11-14',period=None,last=None)])
  self.assertIn('1',attach(IO(),b)['approved_statistics_exceptions'])

class CampaignWindow(unittest.TestCase):
 def source(self):
  from datetime import datetime,timezone
  b,s,cp,ds,event,m=fixture(bid=28,post=metrics(25,clicks=61))
  s['observed_at']=datetime.now(timezone.utc).isoformat()
  cp.update(bid_type='manual',timestamps=dict(started='2026-11-13T12:00:00+03:00'))
  b['campaigns'][0].update(balance=100)
  s['economics']['rows']['11']=copy.deepcopy(s['economics']['rows']['10'])
  for e in s['economics']['rows'].values():e.update(buyout=.3,sample_size=0,buyout_fallback=True,logistics_cny=38,fx_rub_per_cny=12,commission_pct=20)
  for d in s['batches']['a']['stats'][0]['days']:
   ns=d['apps'][0]['nms'];d.update(sum=sum(n['sum']for n in ns),clicks=sum(n['clicks']for n in ns),orders=sum(n['orders']for n in ns),sum_price=sum(n['sum_price']for n in ns))
  m['1:11']=28
  return b,s,m
 def test_campaign_review_excludes_launch_day(self):
  from china_campaign_financial_review import apply as financial
  class IO:
   def get(self,k):return {}
  b,s,m=self.source();out=financial(IO(),b,s,m)
  # 61 clicks does not meet whole-campaign pause threshold; launch-day clicks cannot satisfy it.
  self.assertIsNone(out['campaigns'][0].get('financial_action'))
 def test_campaign_first_full_day_can_pause_at_floor(self):
  from china_campaign_financial_review import apply as financial
  class IO:
   def get(self,k):return {}
  b,s,m=self.source()
  for d in s['batches']['a']['stats'][0]['days']:
   if d['date']=='2026-11-14':d['clicks']=150
  a=financial(IO(),b,s,m)['campaigns'][0]['financial_action']
  self.assertEqual(a['kind'],'pause_campaign');self.assertEqual(a['risk_evidence']['period_from'],'2026-11-14')
  self.assertEqual(a['risk_evidence']['spend_cny'],25)

if __name__=='__main__':unittest.main()

