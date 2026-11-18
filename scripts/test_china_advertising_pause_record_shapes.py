import unittest
from china_campaign_pause_reason import classify
class Shapes(unittest.TestCase):
 def state(self):return {'id':12,'status':11,'timestamps':{'started':'2026-11-01T00:00:00+03:00'}}
 def test_list_request_cannot_prove_owner_pause(self):
  r={'status':'verified','request':[{'path':'/adv/v0/pause?id=12'}],'action':[],'after':{'id':12,'status':11},'owner_id':5122667182,'verified_at':'2026-11-18T09:00:00+03:00'}
  self.assertEqual(classify(self.state(),0,[{'payload':r}])['cause'],'unknown')
 def test_valid_verified_pause_survives_mixed_records(self):
  r={'status':'verified','request':{'path':'/adv/v0/pause?id=12'},'after':{'id':12,'status':11},'owner_id':5122667182,'verified_at':'2026-11-18T09:00:00+03:00'}
  result=classify(self.state(),0,[[],{'payload':[{}]},{'payload':{'request':[]}},{'payload':r,'cache_key':'verified-receipt'}])
  self.assertEqual(result['cause'],'owner_paused');self.assertEqual(result['receipt_key'],'verified-receipt')
if __name__=='__main__':unittest.main()
