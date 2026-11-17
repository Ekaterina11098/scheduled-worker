import copy,unittest
from china_package_readback import check,validate
def cp(ids):return dict(id=1,currency='CNY',status=9,settings={},nm_settings=[dict(nm_id=n,bids_kopecks=dict(recommendations=28))for n in ids])
class PackageTest(unittest.TestCase):
 def fixture(self):
  items=[dict(id=str(n),campaign_id=1,nm_id=n,kind='ad_exclude_sku')for n in(1,2)]
  states=[dict(id='1',status='verified',before=cp([1,2,3]),after=cp([2,3])),dict(id='2',status='verified',before=cp([2,3]),after=cp([3]))]
  return items,states
 def test_success_with_sequential_baselines(self):
  i,s=self.fixture();self.assertFalse(check(i,s,{1:cp([3])})[0])
 def test_previous_exclusion_reappears(self):
  i,s=self.fixture();self.assertTrue(check(i,s,{1:cp([1,3])})[0])
 def test_delayed_reappearance_invalidates_and_never_writes(self):
  i,s=self.fixture();reads=iter([cp([3]),cp([1,3])]);r=validate(i,s,lambda _:next(reads),lambda _:None)
  self.assertEqual(r['status'],'uncertain');self.assertTrue(all(x['status']=='uncertain'and x['historical_step_status']=='verified'for x in s))
 def test_unrelated_bid_change_is_not_silent(self):
  i,s=self.fixture();a=cp([3]);a['nm_settings'][0]['bids_kopecks']['recommendations']=30
  self.assertTrue(check(i,s,{1:a})[0])
 def test_read_failure_is_not_success(self):
  i,s=self.fixture()
  def fail(_):raise RuntimeError('HTTP500')
  self.assertEqual(validate(i,s,fail,lambda _:None)['status'],'uncertain')
if __name__=='__main__':unittest.main()

