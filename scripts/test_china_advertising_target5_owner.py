import unittest,copy
from datetime import datetime,timezone
from owner_risk16_target5 import target5,CID,KEEP

class Target5(unittest.TestCase):
 def fixture(self):
  ids=sorted(KEEP|set(range(100,112)));now=datetime.now(timezone.utc).isoformat()
  c=dict(id=CID,current_articles=[dict(nm=n,article=str(n))for n in ids],budget_members=[dict(nm=n,first_full_day='2026-11-15',completed_traffic=dict(spend=1,orders=0,amount=0,clicks=4),economics=dict(expected_margin_before_ads_cny=10,stock_free=20,published_stock=20,observed_at=now))for n in ids],focus=[dict(nm=999,action=dict(id='add637',kind='ad_add_sku'))],attention=[])
  other=dict(id=41332083,focus=[dict(nm=1473243903,action=dict(id='534',kind='ad_add_sku'))],attention=[])
  b=dict(campaigns=[c,other],recommendation_directions={k:dict(rows=[])for k in ('add','exclude','raise','reduce')})
  b['recommendation_directions']['add']['rows']=[dict(campaign_id=CID,nm_id=999,ready=True),dict(campaign_id=41332083,nm_id=1473243903,ready=True)]
  return b
 def test_target_strategy_proposes_twelve_exclusions_and_stops_conflicting_expansion_only_here(self):
  b=self.fixture();before=copy.deepcopy(b);r=target5(b)
  self.assertEqual(len(r['campaigns'][0]['attention']),12)
  self.assertFalse(any(x['action']['kind']=='ad_add_sku'for x in r['campaigns'][0]['attention']))
  self.assertEqual(r['recommendation_directions']['add']['rows'],before['recommendation_directions']['add']['rows'][1:])
  self.assertEqual(r['campaigns'][1],before['campaigns'][1]);self.assertEqual(b,before)
  self.assertTrue(r['owner_umbrella_target5']['retrospective_not_forecast'])
 def test_no_full_postchange_day_cannot_generate_strategy(self):
  b=self.fixture();b['campaigns'][0]['budget_members'][0]['first_full_day']='2026-11-16'
  with self.assertRaises(AssertionError):target5(b)
if __name__=='__main__':unittest.main()
