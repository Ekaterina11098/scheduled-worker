import ast,copy,pathlib,unittest
module=ast.parse(pathlib.Path(__file__).with_name('china_advertising_decision_contract.py').read_text(encoding='utf-8'))
node=next(n for n in module.body if isinstance(n,ast.FunctionDef)and n.name=='comparable_action')
scope={'copy':copy};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-production-comparable-action','exec'),scope)
class ObservationIdentity(unittest.TestCase):
 def action(self):return dict(kind='ad_set_bid',target_minor=30,growth_evidence=dict(price_cny=200,metrics=dict(orders=5,spend=10),prices_observed_at='old',buyout_observed_at='old',observed_at='old'))
 def test_same_verified_values_remain_same_proposal_after_reobservation(self):
  a=self.action();b=copy.deepcopy(a)
  for k in ('prices_observed_at','buyout_observed_at','observed_at'):b['growth_evidence'][k]='new'
  self.assertEqual(scope['comparable_action'](a),scope['comparable_action'](b))
 def test_price_bid_and_actual_economic_or_metric_changes_still_conflict(self):
  a=self.action()
  for kind in ('price','bid','orders'):
   b=copy.deepcopy(a)
   if kind=='price':b['growth_evidence']['price_cny']=201
   elif kind=='bid':b['target_minor']=31
   else:b['growth_evidence']['metrics']['orders']=6
   self.assertNotEqual(scope['comparable_action'](a),scope['comparable_action'](b))
if __name__=='__main__':unittest.main()

