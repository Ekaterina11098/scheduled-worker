import copy,unittest
from unittest.mock import patch
import fbs_document_chain as m
import test_fbs_chain as fixtures
ref=fixtures.ref

class LinkedReturnTests(unittest.TestCase):
    setUp=fixtures.Tests.setUp
    def manual_return(self):
        self.w.process(self.state)
        manual=self.t.docs['salesreturn'][0]
        manual['externalCode']='manual-external-code'
        self.t.docs['demand'][0]['returns']=[ref('salesreturn',manual['id'])]
        self.state['status']='salesreturn_rejected'
        self.state['error']='HTTP_412 POST entity/salesreturn'
        self.state['documents'].pop('salesreturn')
        self.t.writes=[]
        return manual

    def test_exact_manual_return_is_adopted_without_document_writes(self):
        self.manual_return()
        before=copy.deepcopy(self.t.docs)
        self.w.process(self.state)
        self.w.process(self.state)
        self.assertEqual(self.t.docs,before)
        self.assertEqual(self.t.writes,[])
        self.assertEqual(self.state['status'],'complete')
        self.assertFalse(self.state['reconciled_linked_return']['document_changed'])
        self.assertNotIn('error',self.state)

    def test_inexact_manual_return_stops_without_creating_another(self):
        for field in ('quantity','store','applicable','description'):
            with self.subTest(field=field):
                self.setUp();manual=self.manual_return()
                if field=='quantity':manual['positions'][0]['quantity']=1
                elif field=='store':manual['store']=ref('store','wrong')
                elif field=='applicable':manual['applicable']=False
                else:manual['description']='different supply'
                with self.assertRaises(m.Stop):self.w.process(self.state)
                self.assertEqual(self.t.writes,[])

    def test_multiple_linked_returns_require_manual_reconciliation(self):
        self.manual_return()
        self.t.docs['demand'][0]['returns'].append(ref('salesreturn','second'))
        with self.assertRaisesRegex(m.Stop,'manual reconciliation'):self.w.process(self.state)
        self.assertEqual(self.t.writes,[])

    def test_posted_demand_retry_does_not_require_the_same_stock_twice(self):
        self.manual_return()
        route={k:m.href(self.c['templates'][k]['store']) for k in m.TYPES}
        with patch.object(self.w,'china_warehouse_routing',return_value=route),patch.object(self.w,'require_available_stock',side_effect=AssertionError('Already posted demand must not consume stock again')):
            self.w.process(self.state)
        self.assertEqual(self.t.writes,[])

    def test_deleted_demand_still_requires_stock_before_new_post(self):
        self.manual_return();self.t.docs['demand']=[]
        route={k:m.href(self.c['templates'][k]['store']) for k in m.TYPES}
        with patch.object(self.w,'china_warehouse_routing',return_value=route),patch.object(self.w,'require_available_stock',side_effect=m.Stop('Insufficient stock')):
            with self.assertRaisesRegex(m.Stop,'Insufficient stock'):self.w.process(self.state)
        self.assertEqual(self.t.writes,[])

if __name__=='__main__':unittest.main()
