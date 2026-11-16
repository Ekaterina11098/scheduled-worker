import copy,unittest
from unittest.mock import patch
from owner_risk16_report import reviewed,EXPECTED,HELD_NM
class Holds(unittest.TestCase):
 def test_same_report_review_keeps_two_cost_actions_once_and_removes_owner_held_addition(self):
  rows=[dict(nm=nm,article=str(nm),decision='Исключить',period={},economics={},action=dict(id=str(cid)+':'+str(nm),campaign_id=cid,nm_id=nm,kind='ad_exclude_sku'))for cid,nm in EXPECTED]
  held=dict(nm=HELD_NM,article='534',action=dict(kind='ad_add_sku',nm_id=HELD_NM,campaign_id=41332083))
  b=dict(campaigns=[dict(id=41325637,focus=[]),dict(id=41332083,focus=rows+[held])],recommendation_directions={k:dict(rows=[])for k in ('raise','reduce','add','exclude')})
  b['recommendation_directions']['add']['rows']=[dict(nm_id=HELD_NM,campaign_id=41332083,ready=True)]
  b['recommendation_directions']['exclude']['rows']=[dict(nm_id=nm,campaign_id=cid,ready=True)for cid,nm in EXPECTED]
  with patch('china_advertising_economic_review.apply',side_effect=lambda b,s,m:copy.deepcopy(b)):
   r=reviewed(b,{},{});
  self.assertEqual(len(r['recommendation_directions']['exclude']['rows']),2)
  self.assertEqual(r['recommendation_directions']['add']['rows'],[])
  self.assertFalse(any(x['nm']==HELD_NM for c in r['campaigns']for x in c['focus']))
  self.assertEqual(len(b['campaigns'][1]['focus']),3)
if __name__=='__main__':unittest.main()
