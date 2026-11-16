import copy,unittest
from datetime import datetime,timezone
from owner_risk16_restore import restore,NM,CID

class CurrentOwner(unittest.TestCase):
 def fixture(self):
  e=dict(expected_margin_before_ads_cny=31,stock_free=700,published_stock=42,buyout_fallback=False,observed_at=datetime.now(timezone.utc).isoformat())
  row=dict(nm=NM,article='534',action=dict(kind='ad_add_sku',campaign_id=CID,nm_id=NM,growth_evidence=e))
  c=dict(id=CID,focus=[dict(nm=1473246032,action=dict(kind='ad_exclude_sku'))],attention=[])
  current=dict(campaigns=[c],recommendation_directions={'add':dict(rows=[])},owner_cost_review=dict(held_nm_excluded=NM))
  prior=dict(campaigns=[dict(id=CID,focus=[row])],recommendation_directions={'add':dict(rows=[dict(nm_id=NM,campaign_id=CID,ready=True)])})
  return current,prior
 def test_owner_correction_restores_checked_proposal_and_keeps_cost_action(self):
  c,p=self.fixture();before=copy.deepcopy(c);r=restore(c,p)
  self.assertEqual(len(r['campaigns'][0]['focus']),2)
  self.assertEqual(r['campaigns'][0]['focus'][0]['action']['kind'],'ad_exclude_sku')
  self.assertEqual(r['recommendation_directions']['add']['rows'][0]['nm_id'],NM)
  self.assertNotIn('held_nm_excluded',r['owner_cost_review']);self.assertEqual(c,before)
 def test_unready_economics_cannot_be_restored_as_ready(self):
  c,p=self.fixture();p['campaigns'][0]['focus'][0]['action']['growth_evidence']['expected_margin_before_ads_cny']=-1
  with self.assertRaises(AssertionError):restore(c,p)
if __name__=='__main__':unittest.main()
