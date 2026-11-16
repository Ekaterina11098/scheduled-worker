import unittest
from unittest.mock import patch
import stock_guangzhou_owner_restore as r
from stock_operation_store import Stopped
from stock_china_mgt import policy,WB_WAREHOUSE
from stock_china_mgt_daily import approval
class Store:
 def __init__(self):self.state='sent';self.events=[]
 def operations(self,root):return [(0,{'location':{'chrtId':7,'warehouse':2373413},'target':5},self.state,{})]
 def transition(self,root,seq,old,new,detail):self.state=new;self.events.append(detail)
class G:
 WB_MARKET='https://example.invalid'
 def cabinet_tokens(self):return ['a','b','c']
 def api(self,method,url,token,**kw):
  if method!='POST':raise AssertionError('Reconciliation attempted a write')
  return {'stocks':[{'chrtId':7,'amount':self.actual}]}
class Tests(unittest.TestCase):
 def test_route_and_both_reservation_sources(self):
  p=policy();self.assertEqual(WB_WAREHOUSE,2373413)
  self.assertEqual(p['order_warehouse_ids'],[2308581,2373413])
  self.assertEqual(p['pool_id'],'china-mgt-2308581')
  self.assertEqual(approval('technical:stock-daily:2026-11-17')['warehouse'],2373413)
  self.assertEqual(approval('technical:stock-daily:2026-11-17:0700')['warehouse'],2373413)
 def test_unknown_outcome_never_resends(self):
  s=Store();g=G();g.actual=4
  with self.assertRaises(Stopped):r.reconcile(g,s)
  self.assertEqual(s.state,'uncertain')
 def test_confirmed_readback(self):
  s=Store();g=G();g.actual=5;r.reconcile(g,s);self.assertEqual(s.state,'confirmed')
 def test_reject_unapproved_destination(self):
  with patch.object(r,'require_cloud_lease'):
   with self.assertRaises(Stopped):r.validate_intent({'owner_restore_root':r.ROOT,'warehouse':2308581})
 def test_renamed_warehouse_keeps_same_identity(self):
  from stock_china_mgt import select_warehouse
  self.assertEqual(select_warehouse([{'id':2373413,'name':'Переименованный склад'}])['id'],2373413)
 def test_name_cannot_select_wrong_id(self):
  from stock_china_mgt import select_warehouse
  with self.assertRaises(Stopped):select_warehouse([{'id':2308581,'name':'Гуанджоу новый'}])
 def test_deleting_or_duplicate_id_is_rejected(self):
  from stock_china_mgt import select_warehouse
  with self.assertRaises(Stopped):select_warehouse([{'id':2373413,'isDeleting':True}])
  with self.assertRaises(Stopped):select_warehouse([{'id':2373413},{'id':2373413}])
unittest.main()
