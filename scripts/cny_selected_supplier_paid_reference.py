"""Narrow selected supplier payment reference correction. Private inputs and results only."""
import copy,sys,time
import cny_all_remaining_refs_apply as a
from cny_journal_clean_get import JournalTransport
b=a.b;m=a.m;r=a.r
Q='selected_supplier_paid_20261128:'
def save(db,k,v): b.put(db,Q+k,v)
def main():
 t=JournalTransport();db=m.Cache(t)
 cfg=db.get(b.ROOT+Q+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='selected_supplier_paid_reference_only'
 assert not db.get(b.ROOT+Q+'result:v1'),'Already completed; do not replay'
 ids=list(cfg['payments']);oid=cfg['order_id']
 order=r.live(t,'purchaseorder',[oid])[oid]
 assert order['name']==cfg['order_name'] and order['sum']==cfg['expected_sum']
 currencies=b.fullrows(t,'entity/currency')
 base=next(c for c in currencies if c.get('default'))
 assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 assert r.currency(order)==m.href(base) and b.D(order['rate'].get('value',1))==1
 supplies=[m.href(x).split('?')[0].rsplit('/',1)[1] for x in order.get('supplies',[])]
 supplied=r.live(t,'supply',supplies) if supplies else {}
 before=r.live(t,'paymentout',ids)
 for i,d in before.items():
  assert d['sum']==cfg['payments'][i]
  ops=d.get('operations',[])
  assert len(ops)==1 and m.href(ops[0]).split('?')[0]==m.MS+'entity/purchaseorder/'+oid
  assert ops[0]['linkedSum']==d['sum']
  assert next(c for c in currencies if m.href(c)==r.currency(d))['isoCode']=='CNY'
  assert b.D(d['rate'].get('value',1)) in (1,12)
 bodies=[a.body(d,base,'paymentout') for d in before.values() if r.currency(d)!=m.href(base) or b.D(d['rate'].get('value',1))!=1]
 snapshot={'at':m.now(),'before':before,'order':order,'supplies':supplied,'bodies':bodies}
 prior=db.get(b.ROOT+Q+'snapshot:v1')
 intent=db.get(b.ROOT+a.P+Q+'write:intent')
 if prior:
  assert not bodies,'Previous preparation exists; reconcile without replay'
  snapshot=prior;before=prior['before'];order=prior['order'];supplied=prior['supplies']
 else:
  assert not intent
  save(db,'snapshot:v1',snapshot)
  assert db.get(b.ROOT+Q+'snapshot:v1')==snapshot
  if bodies:
   a.write(db,'paymentout',bodies,Q+'write')
 after=r.live(t,'paymentout',ids)
 for i,z in after.items():
  a.invariant(before[i],z,'paymentout')
  assert r.currency(z)==m.href(base) and b.D(z['rate'].get('value',1))==1
 final=None
 for _ in range(6):
  final=r.live(t,'purchaseorder',[oid])[oid]
  if final['payedSum']==cfg['expected_sum']: break
  time.sleep(5)
 a.invariant(order,final,'purchaseorder')
 assert final['shippedSum']==order['shippedSum']
 assert final['payedSum']==cfg['expected_sum']
 supplied_after=r.live(t,'supply',list(supplied)) if supplied else {}
 for i,z in supplied_after.items():
  a.invariant(supplied[i],z,'supply')
  assert a.signature(supplied[i],'supply')==a.signature(z,'supply')
 save(db,'readback:v1',{'at':m.now(),'payments':after,'order':final,'supplies':supplied_after})
 save(db,'result:v1',{'status':'verified','at':m.now(),'sum':final['sum'],'payedSum':final['payedSum'],'shippedSum':final['shippedSum'],'payments':{i:z['sum'] for i,z in after.items()},'nominal_amounts_items_quantities_stores_preserved':True})
 print('Selected payment references and derived paid total verified; nominal values preserved.')
if __name__=='__main__':
 try: main()
 except Exception as e:
  try: save(m.Cache(JournalTransport()),'error:v1',{'at':m.now(),'status':'stopped','reason':str(e)})
  except Exception: pass
  print('Stopped; reconcile private checkpoint before any retry.')
  sys.exit(1)
