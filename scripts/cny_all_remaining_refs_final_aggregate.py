"""Combine all read-only reconciliation partitions and close write authorization."""
import sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;h=a.h;r=a.r;b=a.b;m=a.m
def main():
 t=b.ReadOnly();db=m.Cache(t)
 existing=db.get(b.ROOT+p.P+'result:v1')
 if existing:
  assert existing['status']=='verified';print('Existing complete reconciliation preserved.');return
 start=db.get(b.ROOT+p.P+'reconciled_start:v1') or db.get(b.ROOT+p.P+'start:v1')
 parts=[db.get(b.ROOT+p.P+'final_part:'+g) for g in ('orders','shipments','other')]
 assert all(x and x['status']=='verified' and x['all_store_quantities_preserved'] and x['all_documents_preserved'] and x['all_document_prices_nominal_sums_quantities_rows_stores_links_preserved'] for x in parts)
 summary=[s for x in parts for s in x['types']]
 assert len(summary)==len(start['types']) and {s['type'] for s in summary}==set(start['types'])
 pf=db.get(b.ROOT+p.P+'preflight:v1')
 assert sum(s['normalized'] for s in summary)==sum(s['candidates'] for s in pf['types'])
 assert h.warehouse(t)==start['warehouse_quantities']
 assert h.h.ccstate(b.fullrows(t,'entity/currency'))==h.h.ccstate(start['currencies'])
 result={'status':'verified','at':m.now(),'types':summary,'normalized':sum(s['normalized'] for s in summary),'all_document_prices_nominal_sums_quantities_rows_stores_links_preserved':True,'all_store_quantities_preserved':True,'all_documents_preserved':True,'all_currency_references_base_cny_rate_one':True,'business_conversion_rub_per_cny':12,'outside_ms_changes':False,'partitioned_final_reconciliation':True,'independent_read_phase_movement_reconciled':bool(db.get(b.ROOT+p.P+'baseline_reconciliation:v1'))}
 p.save(db,'result:v1',result)
 auth=db.get(b.ROOT+p.P+'authorization:v1');auth.update(authorized=False,completed=True,completed_at=m.now());p.save(db,'authorization:v1',auth)
 print('All reference corrections and document/warehouse reconciliation verified.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:final_aggregate:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Final aggregate verification stopped.');sys.exit(1)
