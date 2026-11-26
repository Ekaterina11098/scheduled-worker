"""Read-only source order and shipment context for unconverted-looking customer returns."""
import sys,traceback
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='all_document_currency_audit_post_incoming:'
def main():
 t=b.ReadOnly();db=m.Cache(t);result=db.get(b.ROOT+P+'result:salesreturn');assert result['status']=='complete'
 flagged=[]
 for offset in range(0,result['documents'],1000):
  page=db.get(b.ROOT+P+'records:salesreturn:'+str(offset))
  flagged.extend(d for d in page['rows'] if 'amount_equals_original_ruble_total' in d['flags'])
 returns=r.live(t,'salesreturn',[d['id'] for d in flagged])
 demand_ids=sorted({m.href(d['demand']).split('/')[-1] for d in returns.values() if d.get('demand')})
 demands=r.live(t,'demand',demand_ids)
 order_ids=sorted({m.href(d['customerOrder']).split('/')[-1] for d in demands.values() if d.get('customerOrder')})
 orders=r.live(t,'customerorder',order_ids) if order_ids else {}
 summary=[]
 for i,d in returns.items():
  dm=demands.get(m.href(d.get('demand',{})).split('/')[-1],{});od=orders.get(m.href(dm.get('customerOrder',{})).split('/')[-1],{})
  vals=[]
  for p in r.rows(d):
   matches=[q for q in r.rows(od) if m.href(q['assortment'])==m.href(p['assortment'])]
   vals.append({'return_quantity':p['quantity'],'return_price':p['price'],'order_matches':[{'price':q['price'],'quantity':q['quantity'],'discount':q.get('discount'),'vat':q.get('vat')} for q in matches]})
  summary.append({'id':i,'name':d['name'],'moment':d['moment'],'sum_minor':d['sum'],'positions':len(r.rows(d)),'quantity':float(sum(b.D(p['quantity']) for p in r.rows(d))),'demand_id':dm.get('id'),'demand_name':dm.get('name'),'demand_sum_minor':dm.get('sum'),'order_id':od.get('id'),'order_name':od.get('name'),'order_sum_minor':od.get('sum'),'line_comparison':vals})
 b.put(db,P+'suspect_returns_detail:v1',{'at':m.now(),'summary':summary,'returns':returns,'demands':demands,'orders':orders,'ms_writes':0})
 print('Suspect return source chains inspected read only; results private.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:b.put(m.Cache(b.ReadOnly()),P+'error:suspect_returns:v1',{'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only return detail inspection stopped.');sys.exit(1)
