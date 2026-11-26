"""Read-only follow-up of linked return and invoice currency anomalies."""
import sys,traceback
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='all_document_currency_audit_post_incoming:'
def main():
 t=b.ReadOnly();db=m.Cache(t);docs={};related={}
 for typ in ('purchasereturn','factureout'):
  ids=[d['id'] for d in db.get(b.ROOT+P+'records:'+typ+':0')['rows']]
  docs[typ]=r.live(t,typ,ids)
  for d in docs[typ].values():
   for k in ('supply','demand'):
    if d.get(k):related.setdefault(d[k]['meta']['type'],set()).add(m.href(d[k]).split('/')[-1])
   for dref in d.get('demands',[]):related.setdefault('demand',set()).add(m.href(dref).split('/')[-1])
 live={typ:r.live(t,typ,list(ids)) for typ,ids in related.items()}
 b.put(db,P+'linked_anomaly_detail:v1',{'at':m.now(),'documents':docs,'related':live,'ms_writes':0})
 print('Read-only linked anomaly details saved privately.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:b.put(m.Cache(b.ReadOnly()),P+'error:linked:v1',{'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only detail audit stopped.');sys.exit(1)
