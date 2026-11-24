import copy
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

helper = types.ModuleType('china_cloud_cost_control')
helper.Cache = lambda: (_ for _ in ()).throw(AssertionError('Unexpected live access'))
helper.WB = object
helper.validate_identity = lambda *a: None
helper.stamp = lambda: datetime.now(timezone.utc).isoformat()
with patch.dict(sys.modules, {'china_cloud_cost_control': helper, 'requests':types.ModuleType('requests')}):
    import china_hourly_saved_analysis as m


class SavedAnalysis(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.cut = self.now.astimezone(m.MSK).replace(minute=0, second=0, microsecond=0)
        self.key = m.ROOT + ':snapshot:' + self.cut.strftime('%Y-%m-%dT%H') + ':MSK'
        class Cache:
            def __init__(self): self.data = {}; self.creates = 0; self.puts = 0
            def get(self, key): return copy.deepcopy(self.data.get(key))
            def create(self, key, value):
                if key in self.data: return False
                self.data[key] = copy.deepcopy(value); self.creates += 1; return True
            def put(self, key, value): self.data[key] = copy.deepcopy(value); self.puts += 1
        self.c = Cache()
        self.s = dict(status='complete', cabinet='token_3', slot_msk=self.cut.isoformat(), observed_at=self.now.isoformat(),
            orders={str(n):dict(status='complete', rows=[dict(id=n,convertedPrice=10000,convertedCurrencyCode=156)],
                totals=dict(count=1,amount_cny=100,unknown_amount_ids=[])) for n in (0,1,7)},
            advertising=dict(status='complete',totals=dict(spend_cny=1),missing_ids=[9]),
            budgets=dict(status='complete',rows=[dict(advertId=1,total=100)]))
        self.c.data.update({m.POLICY:dict(enabled=True,cabinet='token_3',wb_writes=0),
            m.ROOT+':latest':dict(source_key=self.key,slot_msk=self.cut.isoformat()),self.key:self.s})
    def test_freezes_analysis_and_second_run_does_not_repeat_or_rewrite_source(self):
        original=copy.deepcopy(self.c.data[self.key]);first=m.run(self.c);calls=(self.c.creates,self.c.puts)
        self.assertEqual(m.run(self.c),first)
        self.assertEqual((self.c.creates,self.c.puts),calls)
        self.assertEqual(self.c.data[self.key],original)
        self.assertEqual(first['model_calls'],0)
        self.assertEqual(first['telegram_calls'],0)
        self.assertEqual(first['wb_writes'],0)
    def test_incomplete_source_is_not_analyzed(self):
        self.s['orders']['0']['status']='partial'
        with self.assertRaises(ValueError):m.run(self.c)
    def test_wrong_cabinet_is_rejected(self):
        self.s['cabinet']='token_2'
        with self.assertRaises(ValueError):m.run(self.c)
    def test_duplicate_order_and_totals_mismatch_rejected(self):
        self.s['orders']['0']['totals']['count']=2
        with self.assertRaises(ValueError):m.run(self.c)
    def test_full_yesterday_funnel_is_not_same_clock_baseline(self):
        row=dict(clicks=10,cart_count=2,orders=1,order_amount_cny=100)
        self.s.update(funnel_requested=True,general_funnel=dict(status='complete',observed_at=self.now.isoformat(),
            rows=[dict(nm_id=5,selected=row,past=dict(clicks=1000,cart_count=100,orders=50))]))
        got=m.run(self.c)
        self.assertEqual(got['funnel_same_clock']['1']['status'],'unavailable_no_saved_same_clock_funnel')
        self.assertEqual(got['funnel_current'][0]['open_cart_pct'],20)
    def test_saved_same_clock_funnel_is_used(self):
        row=dict(clicks=10,cart_count=2,orders=1,order_amount_cny=100)
        self.s.update(funnel_requested=True,general_funnel=dict(status='complete',observed_at=self.now.isoformat(),rows=[dict(nm_id=5,selected=row)]))
        old=copy.deepcopy(self.s);old['slot_msk']=(self.cut-timedelta(days=1)).isoformat()
        old['general_funnel']['observed_at']=(self.now-timedelta(days=1)).isoformat()
        key=m.ROOT+':snapshot:'+(self.cut-timedelta(days=1)).strftime('%Y-%m-%dT%H')+':MSK'
        self.c.data[key]=old
        self.assertEqual(m.run(self.c)['funnel_same_clock']['1']['status'],'comparable_snapshot')


if __name__=='__main__':unittest.main()

