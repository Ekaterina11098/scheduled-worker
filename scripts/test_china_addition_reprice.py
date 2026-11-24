import unittest,copy
from china_addition_reprice import reconcile
class IO:
 def __init__(self,proof=True):
  self.rows={'china_agent:price_write_lock:v1:1':dict(status='done',execution='exec',readback=dict(nmID=1,vendorCode='A',currencyIsoCode4217='CNY',sizes=[dict(discountedPrice=95)])),'exec':dict(status='done')}if proof else {}
 def get(self,k):return self.rows.get(k)
def fixture():
 return dict(nm_id=1,article='A',growth_evidence=dict(price_cny=100,buyout=.5,commission_pct=20,tax_pct=5,payment_reserve_pct=3,expected_margin_before_ads_cny=10,own_cogs_rub=300,fx_rub_per_cny=12)),dict(article='A',seller_price=95),dict(coverage_complete=True,rows=[dict(stock=10,reserve=2,price=30000)]),dict(amounts={'1':4})
class Tests(unittest.TestCase):
 def test_confirmed_reprice_and_input_unchanged(self):
  i,p,s,b=fixture();old=copy.deepcopy(i);e=reconcile(IO(),i,p,s,b)
  self.assertAlmostEqual(e['expected_margin_before_ads_cny'],8.2);self.assertEqual(i,old)
 def test_unknown_price_fails(self):
  with self.assertRaisesRegex(ValueError,'receipt'):reconcile(IO(False),*fixture())
 def test_negative_margin_fails(self):
  i,p,s,b=fixture();i['growth_evidence']['expected_margin_before_ads_cny']=1
  with self.assertRaisesRegex(ValueError,'positive'):reconcile(IO(),i,p,s,b)
 def test_stock_missing_fails(self):
  i,p,s,b=fixture();b['amounts']={}
  with self.assertRaisesRegex(ValueError,'stock'):reconcile(IO(),i,p,s,b)
 def test_cogs_increase_recalculated(self):
  i,p,s,b=fixture();s['rows'][0]['price']=31200
  self.assertAlmostEqual(reconcile(IO(),i,p,s,b)['expected_margin_before_ads_cny'],7.7)
 def test_unfinished_price_receipt_fails(self):
  io=IO();io.rows['exec']['status']='uncertain'
  with self.assertRaisesRegex(ValueError,'receipt'):reconcile(io,*fixture())
if __name__=='__main__':unittest.main()
