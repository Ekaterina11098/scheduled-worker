import copy,sys,types,unittest
from datetime import datetime,timezone
from unittest.mock import patch
import china_advertising_decision_contract as contract
import china_advertising_economic_review as economics
def metrics(n):return {a:n.get(b,0)for a,b in [('spend','sum'),('amount','sum_price'),('orders','orders'),('clicks','clicks'),('views','views')]}
def sums(rows):
 out=dict(spend=0,amount=0,orders=0,clicks=0,views=0)
 for row in rows:
  for k in out:out[k]+=row[k]
 return out
def fixture():
 at=datetime.now(timezone.utc).isoformat();cp=dict(id=1,status=9,settings={'placements':{'search':True}},nm_settings=[dict(nm_id=631,bids_kopecks={'search':30}),dict(nm_id=2,bids_kopecks={'search':28})],restrictions={'can_change_nms':True})
 days=[dict(date=d,apps=[{'nms':[dict(nmId=631,sum=sp,orders=0,sum_price=0,clicks=cl,views=100)]}])for d,sp,cl in [('2026-11-14',50,100),('2026-11-15',17.35,62),('2026-11-16',15.92,57)]]
 source=dict(executions=[dict(nm=631,cid=1,kind='added',at='2026-11-14T22:41:18+00:00')],batches={'0':{'campaigns':{'adverts':[cp]},'stats':[{'advertId':1,'days':days}]}},economics={'rows':{'631':dict(observed_at=at,price_observed_at=at,stock_observed_at=at,stock_free=50,own_cogs_rub=100,seller_price_cny=405.5,expected_margin_before_ads_cny=89,sample_size=6,buyout_fallback=False,commission_policy_fallback=False)}})
 row=dict(nm=631,article='631',period=sums(metrics(n)for d in days for a in d['apps']for n in a['nms']),decision='incoming',action=None)
 bundle=dict(day='2026-11-17',days=['2026-11-14','2026-11-15','2026-11-16'],campaigns=[dict(id=1,status=9,payment='cpc',focus=[row])])
 return bundle,source,{'1:631':28}
class Tests(unittest.TestCase):
 def setUp(self):
  self.mocks=patch.dict(sys.modules,{'china_advertising_v2':types.SimpleNamespace(history=lambda r:r,daily_metrics=metrics,sums=sums),'china_completed_cost_scan':types.SimpleNamespace(expand=lambda b,s,m:copy.deepcopy(b)),'china_advertising_directions':types.SimpleNamespace(attach=lambda b,s:b)})
  self.mocks.start();self.addCleanup(self.mocks.stop)
 def test_631_launch_day_excluded_in_moscow(self):
  b,s,m=fixture();r=economics.apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertEqual(r['decision_window']['days'],['2026-11-16']);self.assertEqual(r['comparison']['after']['spend'],15.92);self.assertIsNone(r['action'])
 def test_today_changes_never_reuse_old_traffic(self):
  b,s,m=fixture();s['executions'][0]['at']='2026-11-17T06:00:00Z';r=economics.apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertTrue(r['pending_first_day']);self.assertIsNone(r['action'])
 def test_change_in_other_placement_also_resets_sku_epoch(self):
  b,s,m=fixture();s['executions'][0]['cid']=99
  self.assertEqual(contract.changed_day(s,s['batches']['0']['campaigns']['adverts'][0],631),'2026-11-15')
 def test_price_experience_uses_same_epoch(self):
  b,s,m=fixture();s['experience']=[{'action':{'kind':'price_change','nm_ids':[631]},'started_at':'2026-11-16T06:00:00Z'}]
  self.assertEqual(contract.normalize(b,s)['campaigns'][0]['focus'][0]['decision_window']['days'],[])
 def test_three_surfaces_have_identical_decisions_and_evidence(self):
  b,s,m=fixture();results=[];db={}
  class IO:
   def get(self,k):return db.get(k)
   def create(self,k,v):db[k]=copy.deepcopy(v);return True
  for surface in ('morning','midday','analyst'):
   x=copy.deepcopy(b);x['campaigns'][0]['focus'][0].update(decision=surface,action=dict(kind='ad_set_bid',old_minor=30,target_minor=28))
   results.append(contract.finalize(IO(),x,s,m)['decision_contract'])
  self.assertEqual(results[0],results[1]);self.assertEqual(results[1],results[2]);self.assertEqual(len(db),1)
 def test_cumulative_spend_is_not_erased_by_three_day_window(self):
  b,s,m=fixture();s['executions']=[]
  for d in s['batches']['0']['stats'][0]['days']:d['apps'][0]['nms'][0]['sum']=50
  r=economics.apply(b,s,m)['campaigns'][0]['focus'][0]
  self.assertEqual(r['action']['target_minor'],28);self.assertTrue(r['completed_exposure_guard']['not_proven_financial_loss']);self.assertIn('0 прямых заказов',r['decision'])
if __name__=='__main__':unittest.main()

