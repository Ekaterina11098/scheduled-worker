import copy
import unittest
from unittest.mock import patch
import fbs_document_chain as m
import test_fbs_chain as fixtures
ref = fixtures.ref


class LinkedDemandTests(unittest.TestCase):
    setUp = fixtures.Tests.setUp

    def manual_chain(self):
        self.w.process(self.state)
        order = self.t.docs['customerorder'][0]
        demand = self.t.docs['demand'][0]
        ret = self.t.docs['salesreturn'][0]
        demand['externalCode'] = 'manual-demand'
        ret['externalCode'] = 'manual-return'
        order['demands'] = [ref('demand', demand['id'])]
        demand['returns'] = [ref('salesreturn', ret['id'])]
        self.state['documents'] = {'customerorder': self.state['documents']['customerorder']}
        self.state.update(status='customerorder_verified', error='Insufficient available stock')
        self.t.writes = []
        return demand

    def test_manual_chain_replayed_twice_without_writes(self):
        self.manual_chain()
        before = copy.deepcopy(self.t.docs)
        with patch.object(self.w, 'require_available_stock', side_effect=AssertionError('repeat stock check')):
            self.w.process(self.state)
            self.w.process(self.state)
        self.assertEqual(self.t.docs, before)
        self.assertEqual(self.t.writes, [])
        self.assertEqual(self.state['status'], 'complete')
        self.assertNotIn('error', self.state)
        self.assertFalse(self.state['reconciled_linked_demand']['document_changed'])

    def test_routed_manual_chain_skips_repeated_stock_check(self):
        self.manual_chain()
        route = {k: m.href(self.c['templates'][k]['store']) for k in m.TYPES}
        with patch.object(self.w, 'china_warehouse_routing', return_value=route), patch.object(self.w, 'require_available_stock', side_effect=AssertionError('repeat stock check')):
            self.w.process(self.state)
        self.assertEqual(self.t.writes, [])
        self.assertEqual(self.state['status'], 'complete')

    def test_mismatched_manual_demand_never_creates_duplicate(self):
        for field in ('quantity', 'store', 'organization', 'agent', 'applicable', 'description', 'customerOrder', 'sum', 'price'):
            with self.subTest(field=field):
                self.setUp()
                doc = self.manual_chain()
                if field == 'quantity': doc['positions'][0]['quantity'] = 1
                elif field == 'price': doc['positions'][0]['price'] = 1
                elif field in ('store', 'organization', 'agent', 'customerOrder'): doc[field] = ref(field, 'wrong')
                elif field == 'applicable': doc[field] = False
                elif field == 'sum': doc[field] = 1
                else: doc[field] = 'wrong'
                with self.assertRaises(m.Stop): self.w.process(self.state)
                self.assertEqual(self.t.writes, [])

    def test_multiple_manual_demands_stop(self):
        self.manual_chain()
        self.t.docs['customerorder'][0]['demands'].append(ref('demand', 'other'))
        with self.assertRaisesRegex(m.Stop, 'manual reconciliation'): self.w.process(self.state)
        self.assertEqual(self.t.writes, [])

    def test_missing_demand_still_requires_stock(self):
        self.manual_chain()
        self.t.docs['customerorder'][0]['demands'] = []
        self.t.docs['demand'] = []
        with patch.object(self.w, 'require_available_stock', side_effect=m.Stop('Insufficient stock')):
            with self.assertRaisesRegex(m.Stop, 'Insufficient stock'): self.w.process(self.state)
        self.assertEqual(self.t.writes, [])


if __name__ == '__main__': unittest.main()
