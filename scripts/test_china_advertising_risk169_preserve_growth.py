import copy,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from owner_risk169_report import review,EXPECTED,CID

class ParallelGrowth(unittest.TestCase):
 def test_cost_actions_preserve667_and_restore_both_ready_umbrella_tests(self):
  now=datetime.now(timezone.utc).isoformat();rows=[dict(nm=n,article=str(n),pending_first_day=False,period={},comparison={},economics={})for n in EXPECTED]
  addition=dict(nm=667,article='667',action=dict(id='keep667',kind='ad_add_sku',campaign_id=CID,nm_id=667))
  b=dict(campaigns=[dict(id=CID,focus=rows+[addition]),dict(id=41325637,focus=[],attention=[])],recommendation_directions={k:dict(rows=[])for k in ('add','reduce','exclude','raise')},owner_umbrella_target5=dict(remove_new_additions=True))
  b['recommendation_directions']['add']['rows']=[dict(campaign_id=CID,nm_id=667,ready=True)]
  candidates=[dict(nm=n,article=str(n),action=dict(id='add'+str(n),kind='ad_add_sku',campaign_id=41325637,nm_id=n,growth_evidence=dict(expected_margin_before_ads_cny=10,stock_free=20,published_stock=20,observed_at=now)))for n in(26,121)]
  p=dict(campaigns=[dict(id=41325637,focus=candidates)],recommendation_directions=dict(add=dict(rows=[dict(campaign_id=41325637,nm_id=n,ready=True)for n in(26,121)])))
  inputs=dict(first_full_days={str(n):'2026-11-13'for n in EXPECTED},stats=dict(days=[]),catalogue=[],economics={},campaign={})
  def checked(part,s,m):
   r=copy.deepcopy(part)
   for row in r['campaigns'][0]['focus']:
    kind,old,target=EXPECTED[row['nm']];a=dict(kind=kind,old_minor=old,campaign_id=CID,nm_id=row['nm'])
    if target is not None:a['target_minor']=target
    row.update(action=a,decision='Готово',economics={})
   return r
  with patch('china_advertising_economic_review.apply',side_effect=checked):out=review(b,p,inputs)
  self.assertTrue(any(r['nm']==667 and r.get('action')for r in out['campaigns'][0]['focus']))
  self.assertEqual({r['nm']for r in out['campaigns'][1]['attention']},{26,121})
  self.assertEqual(len(out['recommendation_directions']['reduce']['rows']),2)
  self.assertEqual(len(out['recommendation_directions']['exclude']['rows']),2)
  self.assertFalse(out['owner_umbrella_target5']['remove_new_additions'])
if __name__=='__main__':unittest.main()
