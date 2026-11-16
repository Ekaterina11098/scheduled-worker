import ast,unittest
from decimal import Decimal
from pathlib import Path
from china_price_economic_target import feasible_prices,choose_target

class FirstPriceCut(unittest.TestCase):
 def test_lattice_never_below_95percent(self):
  old=dict(current_cny=153.5,base_cny=307,discount=50)
  now=dict(current_cny=192,base_cny=384,discount=50)
  values=feasible_prices(old,now)
  self.assertTrue(values)
  self.assertTrue(all(Decimal(str(x['price_cny']))>=Decimal('182.40')for x in values))
 def test_zero_orders_do_not_invent_recovery_at_partial_cut(self):
  old=dict(current_cny=80,base_cny=160,discount=50);now=dict(current_cny=100,base_cny=200,discount=50)
  before=dict(expected_profit_per_day=10,orders_per_day=1,views=100,days=1)
  after=dict(advertising_per_day=0,orders_per_day=0,views=100,days=1)
  r=choose_target(old,now,before,after,buyout_probability=.5,retention=.72,cost=100,dispatch=10,fx=12)
  self.assertEqual(r['status'],'first_decrease_cap_no_supported_intermediate_demand')
 def test_executor_rejects_old_oversized_plan_before_http(self):
  tree=ast.parse(Path(__file__).with_name('china_price_apply.py').read_text(encoding='utf8'))
  funcs=[x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name in ('dec','plan')]
  scope={'Decimal':Decimal};exec(compile(ast.Module(body=funcs,type_ignores=[]),'plan-only','exec'),scope)
  selection=dict(nm_id='1',article='x',target_cny='80',current_cny='100',seller_discount=50,base_cny=200,club_discount=0)
  row=dict(nmID=1,vendorCode='x',currencyIsoCode4217='CNY',editableSizePrice=False,sizes=[dict(price=200,discountedPrice=100)],discount=50,clubDiscount=0)
  with self.assertRaisesRegex(ValueError,'5%'):scope['plan'](selection,row)
  selection['target_cny']='95'
  self.assertEqual(scope['plan'](selection,row)['price'],190)
if __name__=='__main__':unittest.main()

