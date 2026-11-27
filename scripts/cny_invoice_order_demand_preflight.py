"""Read-only current invoice, shipment and order chain verification."""
import collections,sys,traceback
import cny_incoming_refs_apply as h
r=h.r;b=h.b;m=h.m;P='invoice_order_demand_align:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t)
 src=db.get(b.ROOT+'all_document_currency_audit_post_incoming:linked_anomaly_detail:v1')
 iid=next(iter(src['documents']['factureout']))
 invoice=r.live(t,'factureout',[iid])[iid]
 assert len(invoice.get('demands',[]))==1,'Invoice covers multiple shipments'
 did=m.href(invoice['demands'][0]).split('/')[-1];demand=r.live(t,'demand',[did])[did]
 oid=m.href(demand['customerOrder']).split('/')[-1];order=r.live(t,'customerorder',[oid])[oid]
 docs={'factureout':invoice,'demand':demand,'customerorder':order}
 related={}
 for d in (order,demand):
  for x in d.get('payments',[]):
   typ=x['meta']['type'];assert typ in ('paymentin','paymentout','cashin','cashout')
   related.setdefault(typ,set()).add(m.href(x).split('/')[-1])
 linked={typ:r.live(t,typ,sorted(ids)) for typ,ids in related.items()}
 cc=b.fullrows(t,'entity/currency')
 def items(d):
  totals=collections.defaultdict(lambda:b.D(0))
  for p in r.rows(d):totals[m.href(p['assortment'])]+=b.D(p['quantity'])
  return {k:r.number(v) for k,v in totals.items()}
 save(db,'preflight:v1',{'status':'complete','at':m.now(),'documents':docs,'related':linked,'currencies':cc,'warehouse_quantities':h.warehouse(t),'same_order_shipment_items_quantities':items(order)==items(demand),'same_nominal_order_shipment_sum':b.D(order['sum'])==b.D(demand['sum']),'summary':[{'type':typ,'id':d['id'],'name':d['name'],'sum_minor':d['sum'],'rate':d.get('rate'),'positions':len(r.rows(d))} for typ,d in docs.items()],'ms_writes':0})
 print('Invoice source chain read-only preflight complete; private snapshots saved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:preflight:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Invoice chain read-only preflight stopped.');sys.exit(1)
