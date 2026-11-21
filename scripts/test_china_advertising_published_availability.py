import copy,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from china_advertising_economic_review import apply
class PublishedAvailability(unittest.TestCase):
 def run_case(self,amount=0,missing=False,stale=False):
  stamp=(datetime.now(timezone.utc)-timedelta(hours=25 if stale else 0)).isoformat()
  s={'batches':{'x':{'campaigns':{'adverts':[{'id':1,'status':9,'settings':{'placements':{'search':False}},'nm_settings':[{'nm_id':10,'bids_kopecks':{'recommendations':28}},{'nm_id':11,'bids_kopecks':{'recommendations':28}}],'restrictions':{'can_change_nms':True}}]}}},
   'economics':{'rows':{}},'full_growth_inputs':{'published_stock':{'amounts':{} if missing else {'10':amount},'missing_nm_ids':['10'] if missing else [],'observed_at':stamp},'prices':{'observed_at':stamp,'rows':[{'nm_id':10,'currency':'CNY','seller_price':354.5}]}}}
  b={'campaigns':[{'id':1,'status':9,'payment':'cpc','focus':[{'nm':10,'article':'36-EthelBag-brown','period':{'spend':30,'orders':0,'amount':0,'clicks':100}}]}]}
  with patch('china_completed_cost_scan.expand',side_effect=lambda b,*a:copy.deepcopy(b)),patch('china_advertising_decision_contract.normalize',side_effect=lambda b,*a:b):
   return apply(b,s,{'1:10':28})
 def test_explicit_zero_requires_no_invented_economics(self):
  r=self.run_case();x=r['campaigns'][0]['focus'][0]
  self.assertTrue(r['economic_review_complete']);self.assertEqual(x['action']['kind'],'ad_exclude_sku');self.assertTrue(x['economics']['availability_only']);self.assertNotIn('buyout',x['economics'])
 def test_missing_is_not_zero(self):
  r=self.run_case(missing=True);self.assertFalse(r['economic_review_complete']);self.assertIsNone(r['campaigns'][0]['focus'][0]['action'])
 def test_stale_zero_does_not_authorize_exclusion(self):
  self.assertFalse(self.run_case(stale=True)['economic_review_complete'])
 def test_positive_stock_still_requires_economics(self):
  self.assertFalse(self.run_case(amount=3)['economic_review_complete'])
if __name__=='__main__':unittest.main()
