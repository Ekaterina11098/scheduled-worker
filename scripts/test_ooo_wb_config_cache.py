import copy,datetime,unittest
from ooo_wb_config_cache import ROOT,remember,invalidate,resolve,reusable
NOW=datetime.datetime(2026,11,27,11,50,tzinfo=datetime.timezone.utc).timestamp()
AT='2026-11-27T11:29:50+00:00';CHANGE='2026-11-27T13:29:42+03:00'
def cfg(cid=1):return {'id':cid,'currency':'KGS','status':9,'settings':{'name':'fixture','placements':{'search':False,'recommendations':True}},'timestamps':{'updated':CHANGE},'nm_settings':[{'nm_id':9,'bids_kopecks':{'recommendations':325}}]}
class DB:
 def __init__(self):self.rows={}
 def get(self,k):return copy.deepcopy(self.rows.get(k))
 def once(self,k,v):
  if k in self.rows:raise AssertionError('duplicate')
  self.rows[k]=copy.deepcopy(v)
 def update(self,k,v):self.rows[k]=copy.deepcopy(v)
class Cache(unittest.TestCase):
 def test_today_incident_reuses_verified_read_despite_provider_429(self):
  db=DB();remember(db,[cfg()],AT)
  def blocked(ids):raise AssertionError('Redundant provider request would hit429')
  self.assertEqual(resolve(db,[1],{'1':{'status':9,'changeTime':CHANGE}},blocked,NOW)['1'],cfg())
 def test_new_campaign_fetched_without_rereading_unchanged_campaign(self):
  db=DB();remember(db,[cfg()],AT);calls=[]
  def fetch(ids):calls.append(ids);return [cfg(2)]
  out=resolve(db,[1,2],{str(i):{'status':9,'changeTime':CHANGE}for i in(1,2)},fetch,NOW)
  self.assertEqual(calls,[[2]]);self.assertEqual(set(out),{'1','2'})
 def test_external_change_or_pause_invalidates_cached_config(self):
  db=DB();remember(db,[cfg()],AT);entry=db.get(ROOT+'1')
  for meta in ({'status':11,'changeTime':CHANGE},{'status':9,'changeTime':'2026-11-27T14:40:00+03:00'}, {'status':9}):self.assertFalse(reusable(entry,meta,NOW))
 def test_pending_or_uncertain_write_blocks_stale_reuse(self):
  db=DB();remember(db,[cfg()],AT);invalidate(db,[1]);self.assertFalse(reusable(db.get(ROOT+'1'),{'status':9,'changeTime':CHANGE},NOW))
 def test_incomplete_refresh_is_never_cached_or_zeroed(self):
  db=DB()
  with self.assertRaises(RuntimeError):resolve(db,[1,2],{},lambda ids:[cfg(1)],NOW)
  self.assertEqual(db.rows,{})
 def test_wrong_currency_rejected(self):
  db=DB();row=cfg();row['currency']='RUB'
  with self.assertRaises(RuntimeError):resolve(db,[1],{},lambda ids:[row],NOW)
 def test_stale_or_future_observation_not_reused(self):
  db=DB();remember(db,[cfg()],AT);entry=db.get(ROOT+'1');meta={'status':9,'changeTime':CHANGE}
  self.assertFalse(reusable(entry,meta,NOW+90000));self.assertFalse(reusable(entry,meta,NOW-90000))
if __name__=='__main__':unittest.main()
