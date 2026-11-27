"""Read-only reconciliation of stock activity during the initial currency inventory."""
import sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;h=a.h;r=a.r;b=a.b;m=a.m
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+p.P+'drift_config:v1')
 wh=h.warehouse(t);cc=b.fullrows(t,'entity/currency');changed={}
 for typ in ('move','demand','supply','enter','loss','inventory','salesreturn','purchasereturn','customerorder','purchaseorder','paymentin','paymentout'):
  heads=b.fullrows(t,'entity/'+typ,{'filter':'updated>='+cfg['updated_after']})
  full={}
  for off in range(0,len(heads),50):full.update(r.live(t,typ,[x['id'] for x in heads[off:off+50]]))
  changed[typ]=full
 product=t.request(m.MS,'entity/product/'+cfg['product_id'])
 stores=b.fullrows(t,'entity/store')
 p.save(db,'drift_inspection:v1',{'at':m.now(),'warehouse_quantities':wh,'currencies':cc,'changed_documents':changed,'product':product,'stores':stores,'ms_writes':0})
 print('Concurrent stock activity inspected read only; private result saved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:drift:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only activity inspection stopped.');sys.exit(1)
