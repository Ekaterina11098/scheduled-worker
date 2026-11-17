import copy,unittest
from china_advertising_directions import campaign_table
from china_advertising_v2_png import recommendations

class ActionCells(unittest.TestCase):
 def test_high_drr_does_not_turn_waiting_or_completed_changes_into_new_proposals(self):
  c=dict(id=1,status=9,period=dict(spend=10,amount=100),last=dict(spend=6,amount=100),focus=[dict(article='660',decision='Сохранить ставку до оценки 17.11.',action=None,pending_first_day=True),dict(article='586',decision='Сохранить: малая выборка.',action=None)])
  b=dict(campaigns=[c],recommendation_directions={k:dict(rows=[])for k in ('raise','reduce','add','exclude')})
  before=copy.deepcopy(b);result=campaign_table(b)
  self.assertEqual(recommendations(result['campaigns'][0]),['660: Сохранить ставку до оценки 17.11.'])
  self.assertEqual(result['campaigns'][0]['focus'],c['focus'])
  self.assertFalse(any(x.get('action') for x in result['campaigns'][0]['focus']))
  self.assertEqual(b,before)

 def test_real_campaign_risk_action_remains_visible(self):
  b=dict(campaigns=[dict(id=1,status=9,financial_action=dict(kind='pause_campaign'),financial_recommendation='Приостановить РК. Не пополнять.')],recommendation_directions={k:dict(rows=[])for k in ('raise','reduce','add','exclude')})
  self.assertEqual(recommendations(campaign_table(b)['campaigns'][0]),['Приостановить РК. Не пополнять.'])

if __name__=='__main__':unittest.main()
