"""Offline production selection -> economics -> morning -> PNG, with transport forbidden."""
import copy, socket, unittest
from datetime import datetime, timezone
from unittest.mock import patch
from china_advertising_v2 import recommend
from china_advertising_economic_review import apply
from china_advertising_directions import attach, campaign_table
from china_morning_rules_review import review
from china_advertising_v2 import build

class Policy:
 def get(self,key):
  return dict(enabled=True,mode='full_checks_no_model',cabinet='token_3',chat_id=-1004342917488,owner_id=5122667182,paid_api_allowed=False)

def metrics(spend,orders=0,amount=0,clicks=150):
 return dict(spend=spend,orders=orders,amount=amount,clicks=clicks,views=2000)

def fixture(bid=34,post=None,baseline=False):
 now=datetime.now(timezone.utc).isoformat()
 cp=dict(id=1,status=9,currency='CNY',settings=dict(name='Offline early review',payment_type='cpc',placements=dict(search=True)),restrictions=dict(can_change_nms=True),nm_settings=[dict(nm_id=10,bids_kopecks=dict(search=bid)),dict(nm_id=11,bids_kopecks=dict(search=28))])
 ds={'2026-11-12':metrics(1,20,2000),'2026-11-13':metrics(100,40,4000),'2026-11-14':post or metrics(45),'2026-11-15':metrics(9999)}
 if not baseline:ds.pop('2026-11-12')
 event=dict(cid=1,nm=10,kind='bid',at='2026-11-13T12:00:00+03:00',old=28,target=bid,text='Verified change')
 e=dict(observed_at=now,stock_observed_at=now,price_observed_at=now,stock_free=10,own_cogs_rub=120,seller_price_cny=100,expected_margin_before_ads_cny=20,sample_size=20,buyout_fallback=False,commission_policy_fallback=False)
 raw=[dict(date=d,apps=[dict(nms=[dict(nmId=10,sum=p['spend'],sum_price=p['amount'],orders=p['orders'],clicks=p['clicks'],views=p['views'])])])for d,p in ds.items()]
 s=dict(executions=[],verified_composition_changes=[event],catalogue=dict(rows=[dict(nmID=10,vendorCode='TEST-10')]),economics=dict(rows={'10':e}),batches=dict(a=dict(campaigns=dict(adverts=[cp]),stats=[dict(advertId=1,days=raw)])),day_quality=dict(usable=True),full_growth_review=dict(status='complete',input_key='synthetic:no-live-source'),period_to='2026-11-14',addition_scan=dict(status='complete',candidate_ids=[],period_from='2026-11-12',period_to='2026-11-14'))
 b=dict(day='2026-11-15',days=['2026-11-12','2026-11-13','2026-11-14'],source_observed_at='15.11.2026 · OFFLINE TEST',campaigns=[dict(id=1,status=9,payment='cpc',name='Offline early review',zone='поиск',period=metrics(946,60,6000),last=ds['2026-11-14'],balance=500,forecast=135,coverage=10,created='2026-10-01',budget_recommendation='Без пополнения.',budget_action=None,focus=[],attention=[])])
 return b,s,cp,ds,event,{'1:10':28}

class FirstFullDay(unittest.TestCase):
 def built(self,bid=34):
  b,s,cp,ds,event,m=fixture(bid=bid)
  s.update(ids=[1],period_from='2026-11-08',observed_at=datetime.now(timezone.utc).isoformat(),config=dict(minTopUp=10000))
  cp['timestamps']=dict(created='2026-10-01T00:00:00+03:00')
  s['catalogue']['rows'][0]['price']=100
  s['batches']['a']['budgets']=dict(adverts=[dict(advertId=1,total=500,currency='CNY')])
  for day in s['batches']['a']['stats'][0]['days']:day.update(day['apps'][0]['nms'][0])
  return build(s,m),s,m

 def selected(self,**kw):
  b,s,cp,ds,event,m=fixture(**kw)
  r=recommend(cp,cp['nm_settings'][0],ds,b['days'],[event],28,100)
  if r is not None:r['article']='TEST-10';b['campaigns'][0]['focus']=[r]
  return b,s,m

 def test_post_day_evidence_does_not_require_pre_change_baseline(self):
  b,s,m=self.selected();r=b['campaigns'][0]['focus'][0]
  self.assertEqual(r['comparison']['to_days'],['2026-11-14'])
  self.assertEqual(r['comparison']['after'],metrics(45))
  self.assertNotIn('before',r['comparison'])

 def test_first_full_day_loss_reduces_even_if_older_days_were_profitable(self):
  b,s,m=self.selected();r=apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertEqual(r['action']['target_minor'],28)
  self.assertEqual(r['model_profit_for_attributed_orders_cny'],-45)

 def test_first_full_day_at_minimum_can_exclude(self):
  b,s,m=self.selected(bid=28);r=apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertEqual(r['action']['kind'],'ad_exclude_sku')

 def test_low_sample_first_day_does_not_cut(self):
  b,s,m=self.selected(post=metrics(2,clicks=6));self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])

 def test_positive_own_model_despite_high_drr_is_preserved(self):
  b,s,m=self.selected(post=metrics(30,3,300));self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])

 def test_pending_first_day_clears_inherited_action(self):
  b,s,m=self.selected();r=b['campaigns'][0]['focus'][0];r['pending_first_day']=True
  r['action']=dict(kind='ad_set_bid',old_minor=34,target_minor=28)
  self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])

 def test_missing_initial_shortlist_uses_same_first_day(self):
  b,s,cp,ds,event,m=fixture();r=apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertEqual(r['comparison']['to_days'],['2026-11-14'])
  self.assertEqual(r['action']['target_minor'],28)
  self.assertEqual(r['model_profit_for_attributed_orders_cny'],-45)

 def test_global_price_change_blocks_scan_until_full_day_finishes(self):
  b,s,cp,ds,event,m=fixture();s['experience']=[dict(payload=dict(started_at='2026-11-14T12:00:00+03:00',action=dict(kind='price_change',nm_ids=[10])))]
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'],[])

 def test_new_composition_blocks_scan_until_full_day_finishes(self):
  b,s,cp,ds,event,m=fixture();s['verified_composition_changes'][0].update(kind='added',at='2026-11-14T12:00:00+03:00')
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'],[])

 def test_completed_day_after_price_change_is_eligible(self):
  b,s,cp,ds,event,m=fixture();s['experience']=[dict(started_at='2026-11-13T23:59:00+03:00',action=dict(kind='price_change',nm_ids=[10]))]
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'][0]['comparison']['to_days'],['2026-11-14'])

 def test_morning_preserves_first_day_recommendation_in_actual_campaign(self):
  for bid,key in [(34,'reduce'),(28,'exclude')]:
   b,s,m=self.selected(bid=bid)
   with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
    out=review(Policy(),attach(apply(b,s,m),s),s)
    self.assertEqual(out['recommendation_directions'][key]['ready_count'],1)
    self.assertEqual(out['morning_review']['model_calls'],0)
    self.assertIn('TEST-10',campaign_table(out)['campaigns'][0]['direction_recommendations'][0])
    self.assertIn('Ранняя оценка: 1 полный день.',campaign_table(out)['campaigns'][0]['direction_recommendations'][0])

 def test_full_build_to_morning_to_png_page_actions(self):
  from china_advertising_v2_png import render
  from pathlib import Path
  for bid,kind in [(34,'ad_set_bid'),(28,'ad_exclude_sku')]:
   with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
    b,s,m=self.built(bid)
    out=review(Policy(),attach(apply(b,s,m),s),s)
    out['mandatory_campaign_format']=True
    files=render(out)
    page=next(f for f in files if f['family']=='drr')
    self.assertEqual([a['kind']for a in page['actions']],[kind])
    self.assertEqual(page['actions'][0]['nm_id'],10)
    Path('offline-first-day-'+str(bid)+'.png').write_bytes(page['bytes'])

if __name__=='__main__':unittest.main()
