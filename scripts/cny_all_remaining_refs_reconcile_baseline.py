"""Reconcile independently posted movement during the read-only inventory."""
import copy,sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;h=a.h;r=a.r;b=a.b;m=a.m
def main():
 t=b.ReadOnly();db=m.Cache(t);old=db.get(b.ROOT+p.P+'start:v1');pf=db.get(b.ROOT+p.P+'preflight:v1');diag=db.get(b.ROOT+p.P+'drift_inspection:v1')
 assert pf['status']=='complete' and not pf['errors']
 assert not db.get(b.ROOT+p.P+'baseline_reconciliation:v1')
 assert not any(dd for typ,dd in diag['changed_documents'].items() if typ!='move'),'Other concurrent edits require separate review'
 existing=set(db.get(b.ROOT+p.P+'type:move')['ids']);moves=diag['changed_documents']['move']
 assert moves and all(i not in existing for i in moves),'Only new, independent movements may reconcile this inventory'
 expected=copy.deepcopy(old['warehouse_quantities']);base=old['base']
 for i,d in moves.items():
  assert d.get('applicable') and r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1
  source=m.href(d['sourceStore']);target=m.href(d['targetStore'])
  for row in r.rows(d):
   product=m.href(row['assortment']);q=b.D(row['quantity'])
   assert q>0 and product in expected and source in expected[product] and target in expected[product]
   expected[product][source]=r.number(b.D(expected[product][source])-q)
   expected[product][target]=r.number(b.D(expected[product][target])+q)
 assert expected==pf['warehouse_quantities_after']==diag['warehouse_quantities'],'Concurrent movement does not exactly explain stock difference'
 live=r.live(t,'move',list(moves))
 for i,d in live.items():a.invariant(moves[i],d,'move');assert a.signature(moves[i],'move')==a.signature(d,'move')
 wh=h.warehouse(t);assert wh==expected,'Stock changed again before write baseline'
 assert h.h.ccstate(b.fullrows(t,'entity/currency'))==h.h.ccstate(old['currencies'])
 result={'status':'verified','at':m.now(),'independent_movements':live,'before':old['warehouse_quantities'],'after':wh,'ms_writes':0,'difference_fully_explained_by_new_posted_movements':True}
 p.save(db,'baseline_reconciliation:v1',result)
 revised=copy.deepcopy(old);revised['warehouse_quantities']=wh;revised['reconciled_at']=m.now()
 p.save(db,'reconciled_start:v1',revised)
 print('Concurrent movement fully reconciled without writes; current stock baseline preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:reconcile_baseline:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Baseline reconciliation stopped; no MS writes.');sys.exit(1)
