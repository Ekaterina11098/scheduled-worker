import copy,os,types,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import owner_bags17_launch as m
class Cache:
 rows={}
 def get(self,k):return copy.deepcopy(self.rows.get(k))
 def create(self,k,v):
  if k in self.rows:return False
  self.rows[k]=copy.deepcopy(v);return True
 def put(self,k,v):self.rows[k]=copy.deepcopy(v)
class Transport:
 writes=[];state=None;cash=0;fail=False
 def __init__(self,io):pass
 def config(self):return dict(currency='CNY',minTopUp=10000,cpcStep=1,cpcMaxBid=1290)
 def campaign(self,cid):return copy.deepcopy(self.state)
 def budget(self,cid):return self.cash
 def request(self,path,method='GET',body=None):
  if path=='/adv/v1/promotion/count':return dict(adverts=[dict(advert_list=[dict(advertId=41298169)])])
  if path.startswith('/api/advert/v2/adverts'):return dict(adverts=[dict(id=41298169,status=9,settings=dict(name='existing'),nm_settings=[dict(nm_id=1,subject=dict(id=50))])])
  if path=='/api/advert/v1/bids/min':return dict(bids=[dict(nm_id=n,bids=[dict(type='search',currency='CNY',value=28)])for n in body['nm_ids']])
  self.writes.append((path,method,copy.deepcopy(body)))
  if path=='/adv/v2/seacat/save-ad':
   Transport.state=dict(id=999,status=4,currency='CNY',bid_type='manual',settings=dict(name=m.NAME,payment_type='cpc',placements=dict(search=True,recommendations=False)),nm_settings=[dict(nm_id=n,subject=dict(id=50),bids_kopecks=dict(search=28,recommendations=0))for n in sorted(m.IDS)])
   return 999
  if path=='/api/advert/v1/bids':return {}
  if path.startswith('/adv/v1/budget/deposit'):
   Transport.cash+=body['sum']
   if self.fail:raise RuntimeError('lost response after accepted deposit')
   return {}
  if path.startswith('/adv/v0/start'):
   Transport.state['status']=9;Transport.state['timestamps']=dict(started=datetime.now(timezone.utc).isoformat());return {}
  raise AssertionError(path)
class Flow(unittest.TestCase):
 def setUp(self):
  Transport.writes=[];Transport.cash=0;Transport.state=None;Transport.fail=False
  at=datetime.now(timezone.utc)
  Cache.rows={m.ROOT+'approval':dict(status='approved',owner_id=5122667182,nm_ids=sorted(m.IDS),bid_minor=28,funding_cny=500,placement='search',subject_id=50,no_daily_limits=True,telegram_notifications=False,name=m.NAME,proposal_key='p',expires_at=(at+timedelta(hours=1)).isoformat()),'p':dict(items=[dict(nm_id=n)for n in m.IDS],sources=['fresh']),'fresh':dict(status='complete',completed_at=at.isoformat(),economics=dict(rows={str(n):dict(expected_margin_before_ads_cny=1,stock_free=1,published_stock=1)for n in m.IDS}))}
 def run_flow(self):
  with patch.object(m,'Cache',Cache),patch.object(m,'Transport',Transport),patch.object(m,'validate_identity'),patch.object(m,'WB'),patch.dict(os.environ,{'WB_TOKEN_3':'fake','SUPABASE_URL':'https://private.invalid'}),patch.object(m.requests,'get',return_value=types.SimpleNamespace(ok=True,json=lambda:dict(currency='CNY',net=1000))),patch.object(m.time,'sleep'):
   m.main()
 def test_exact_ten_500_four_writes_and_repeat_has_no_mutations(self):
  self.run_flow();self.assertEqual(len(Transport.writes),4);self.assertEqual(Transport.cash,500)
  e=Cache.rows[m.ROOT+'execution'];self.assertEqual(e['status'],'verified');self.assertTrue(e['reporting_registered'])
  self.assertEqual(Cache.rows['china_agent:verified_campaign_state:v1']['999'],m.ROOT+'campaign:999')
  with self.assertRaisesRegex(RuntimeError,'Existing execution'):self.run_flow()
  self.assertEqual(len(Transport.writes),4)
 def test_uncertain_deposit_prevents_start_and_duplicate_funding(self):
  Transport.fail=True
  with self.assertRaisesRegex(RuntimeError,'lost response'):self.run_flow()
  self.assertEqual(Cache.rows[m.ROOT+'execution']['status'],'uncertain');self.assertEqual(Transport.cash,500)
  self.assertEqual(len(Transport.writes),3);self.assertEqual(Transport.state['status'],4)
  with self.assertRaisesRegex(RuntimeError,'Existing execution'):self.run_flow()
  self.assertEqual(Transport.cash,500);self.assertEqual(len(Transport.writes),3)
if __name__=='__main__':unittest.main()
