import unittest
from china_advertising_directions import risk_summary
class RiskAddition(unittest.TestCase):
 def test_new_addition_has_no_historical_period(self):
  c={'status':9,'period':{'spend':30,'orders':1},'drr':7,'focus':[{'article':'new','decision':'Тест: добавить','period':None},{'article':'old','decision':'Снизить','period':{'spend':30}}]}
  self.assertEqual(risk_summary(c,{'days':['2026-11-20']}),['old: Снизить'])
if __name__=='__main__':unittest.main()
