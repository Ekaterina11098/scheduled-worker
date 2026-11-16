"""All campaign categories share economic containment and page-bound buttons."""
import copy,socket,unittest
from unittest.mock import patch
from test_china_advertising_first_full_day_pipeline import fixture,metrics
from china_advertising_v2 import build
from china_advertising_economic_review import apply
from china_advertising_directions import attach,campaign_table
from china_morning_rules_review import review
from china_advertising_v2_png import render
from china_daily_ad_actions import plan
from china_report_buttons import prepare
from china_loss_control import digest
from datetime import datetime,timezone
class IO:
 def __init__(self):self.rows={}
 def get(self,k):
  if k=='china_agent:report_buttons:v1:policy':return dict(enabled=True)
  if k=='china_agent:advertising_morning_review_policy:v1':return dict(enabled=True,mode='full_checks_no_model',cabinet='token_3',chat_id=-1004342917488,owner_id=5122667182,paid_api_allowed=False)
  return self.rows.get(k)
 def create(self,k,v):
  if k in self.rows:return False
  self.rows[k]=copy.deepcopy(v);return True
 def put(self,k,v):self.rows[k]=copy.deepcopy(v)
def case(cid=1,zone='search',bid=28,planned=False,single=False,spend=8,orders=1,amount=100,clicks=35):
 b,s,c,ds,event,m=fixture(bid=bid,post=metrics(spend,orders,amount,clicks))
 c['id']=cid;b['campaigns'][0]['id']=cid;event['cid']=cid
 s['batches']['a']['stats'][0]['advertId']=cid
 c['settings']['placements']=dict(search=zone=='search',recommendations=zone=='recommendations')
 for n in c['nm_settings']:n['bids_kopecks']={zone:bid}
 if single:c['nm_settings']=c['nm_settings'][:1]
 b['campaigns'][0]['zone']='поиск'if zone=='search'else'рекомендации'
 e=s['economics']['rows']['10'];e.update(expected_margin_before_ads_cny=6,sample_size=0 if planned else 20,buyout_fallback=planned,commission_policy_fallback=planned,buyout=.3,planned_buyout_source='approved-plan'if planned else None)
 return b,s,{str(cid)+':10':28}
class AllCampaigns(unittest.TestCase):
 def setUp(self):self.guard=patch.object(socket.socket,'connect',side_effect=AssertionError('No live network'));self.guard.start()
 def tearDown(self):self.guard.stop()
 def test_all_categories_placements_early_economics_to_png_buttons(self):
  for sid in [50,4377,136,37,83]:
   for zone in ['search','recommendations']:
    for planned in [False,True]:
     for bid in [28,34]:
      with self.subTest(subject=sid,zone=zone,planned=planned,bid=bid):
       b,s,m=case(zone=zone,bid=bid,planned=planned)
       for n in s['batches']['a']['campaigns']['adverts'][0]['nm_settings']:n['subject']=dict(id=sid)
       out=apply(b,s,m);r=out['campaigns'][0]['focus'][0]
       self.assertEqual(r['action']['kind'],'ad_exclude_sku'if bid==28 else'ad_set_bid')
       self.assertEqual(r['comparison']['to_days'],['2026-11-14'])
       io=IO();out=review(io,attach(out,s),s)
       pages=render(out);page=next(p for p in pages if p['family']=='drr')
       self.assertEqual(len(page['actions']),1);p=plan(io,out['day'],page,0)
       self.assertEqual(p['plan_sha256'],digest(page['actions']))
       keyboard=prepare(io,p,'drr');texts=[x['text']for row in keyboard['inline_keyboard']for x in row]
       self.assertTrue(any(('Исключить'in t if bid==28 else'Снизить'in t)for t in texts))
       self.assertTrue(all(len(x['callback_data'])<=64 for row in keyboard['inline_keyboard']for x in row))
 def test_low_drr_can_still_fail_own_economics(self):
  b,s,m=case(spend=4,amount=100,clicks=35)
  s['economics']['rows']['10']['expected_margin_before_ads_cny']=2
  s['economics']['rows']['10']['seller_price_cny']=50
  self.assertEqual(apply(b,s,m)['campaigns'][0]['focus'][0]['action']['kind'],'ad_exclude_sku')
 def test_single_sku_pause_has_real_button(self):
  b,s,m=case(single=True);io=IO();out=review(io,attach(apply(b,s,m),s),s)
  page=next(p for p in render(out)if p['family']=='drr')
  self.assertEqual([a['kind']for a in page['actions']],['pause_campaign'])
  p=plan(io,out['day'],page,0);keyboard=prepare(io,p,'drr')
  self.assertTrue(any('Приостановить'in x['text']for row in keyboard['inline_keyboard']for x in row))
  self.assertIsNone(out['campaigns'][0]['budget_action'])
 def test_positive_own_economics_not_cut_solely_for_red_drr(self):
  b,s,m=case(spend=6,amount=100);s['economics']['rows']['10']['expected_margin_before_ads_cny']=20
  self.assertIsNone(apply(b,s,m)['campaigns'][0]['focus'][0]['action'])
 def test_change_day_not_used(self):
  b,s,m=case();s['verified_composition_changes'][0]['at']='2026-11-14T12:00:00+03:00'
  self.assertFalse(any(r.get('action')for r in apply(b,s,m)['campaigns'][0]['focus']))
 def test_protected_sku_not_changed(self):
  b,s,m=case();r=b['campaigns'][0]['focus'];s['batches']['a']['campaigns']['adverts'][0]['nm_settings'][0]['nm_id']=1473245494
  s['batches']['a']['stats'][0]['days']=[]
  self.assertFalse(any(r.get('action')for r in apply(b,s,m)['campaigns'][0]['focus']))
if __name__=='__main__':unittest.main()
