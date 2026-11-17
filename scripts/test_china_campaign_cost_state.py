"""Offline boundary checks: finite completed costs, no transport or live actions."""
import copy,unittest
from china_completed_cost_scan import preserve_completed_cost
from china_advertising_economic_review import completed_zero_exposure
from china_advertising_directions import campaign_table
class IO:
 def __init__(self):self.data={}
 def get(self,k):return copy.deepcopy(self.data.get(k))
 def put(self,k,v):self.data[k]=copy.deepcopy(v)
 def create(self,k,v):self.put(k,v);return True
def source(days,started='2026-11-01T12:00:00+03:00'):
 state=dict(id=1,status=9,timestamps={'started':started},nm_settings=[{'nm_id':10}])
 raw=dict(advertId=1,days=[dict(date='2026-11-'+str(d).zfill(2)+'T00:00:00Z',apps=[{'nms':[dict(nmId=10,sum=1,clicks=4,orders=0)]}])for d in days])
 return dict(executions=[],batches={'0':dict(campaigns={'adverts':[state]},stats=[raw])}),state
class CompletedCosts(unittest.TestCase):
 def test_reread_and_sliding_window_do_not_reset_or_double_count(self):
  io=IO();s,st=source(range(2,9));preserve_completed_cost(io,s,'2026-11-09')
  s,st=source(range(3,10));ledger=preserve_completed_cost(io,s,'2026-11-10')
  self.assertEqual(ledger,preserve_completed_cost(io,s,'2026-11-10'))
  s['completed_cost_ledger']=ledger;r=completed_zero_exposure(s,st,10,'2026-11-10')
  self.assertEqual((r['spend'],r['clicks'],r['completed_days']),(8,32,8))
  self.assertEqual(len(ledger['1']['10']['days']),7)
 def test_wide_reread_does_not_readd_folded_days(self):
  io=IO();s,st=source(range(2,12));a=preserve_completed_cost(io,s,'2026-11-12')
  self.assertEqual(a,preserve_completed_cost(io,s,'2026-11-12'))
 def test_new_verified_epoch_resets_old_cost(self):
  io=IO();s,st=source(range(2,10));preserve_completed_cost(io,s,'2026-11-10')
  s,st=source(range(3,11),'2026-11-08T10:00:00+03:00');l=preserve_completed_cost(io,s,'2026-11-11')
  s['completed_cost_ledger']=l;r=completed_zero_exposure(s,st,10,'2026-11-11')
  self.assertEqual((r['spend'],r['days']),(2,['2026-11-09','2026-11-10']))
 def test_high_risk_paused_campaign_is_not_displayed_as_no_change(self):
  b=dict(day='2026-11-17',days=['2026-11-14','2026-11-15','2026-11-16'],campaigns=[dict(id=1,status=11,period={'spend':100,'orders':0},focus=[],attention=[])],recommendation_directions={})
  r=campaign_table(b)['campaigns'][0]['direction_recommendations']
  self.assertIn('паузе',r[0]);self.assertNotEqual(r,['Без изменений.'])
if __name__=='__main__':unittest.main()

