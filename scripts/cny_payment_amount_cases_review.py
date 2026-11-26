"""Read-only detailed review of deferred payment amount differences."""
import collections,sys,traceback
import cny_refund_reference_preflight as p
r=p.r;b=p.b;m=p.m;P='payment_amount_cases_review:'
def save(db,k,v):b.put(db,P+k,v)
def read(t,typ,ids):
 ids=sorted(set(ids));out={}
 for i in range(0,len(ids),50):out.update(r.live(t,typ,ids[i:i+50]))
 return out
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1');assert cfg and cfg['mode']=='read_only' and len(cfg['cases'])==10
 docs={};requests=collections.defaultdict(set)
 for c in cfg['cases']:requests[c['type']].add(c['id'])
 for typ,ids in requests.items():docs[typ]=read(t,typ,ids)
 ds=set();rs=set()
 for typ in ('paymentin','paymentout'):
  for d in docs[typ].values():
   for op in d['operations']:
    if typ=='paymentin':ds.add(p.ident(op,'demand'))
    else:rs.add(p.ident(op,'salesreturn'))
 docs['salesreturn']=read(t,'salesreturn',rs)
 ds.update(p.ident(d['demand'],'demand') for d in docs['salesreturn'].values())
 docs['demand']=read(t,'demand',ds)
 docs['customerorder']=read(t,'customerorder',[p.ident(d['customerOrder'],'customerorder') for d in docs['demand'].values() if d.get('customerOrder')])
 allrs=set(p.ident(rr,'salesreturn') for d in docs['demand'].values() for rr in d.get('returns',[]))
 docs['salesreturn'].update(read(t,'salesreturn',allrs-set(docs['salesreturn'])))
 rows=[]
 for c in cfg['cases']:
  pay=docs[c['type']][c['id']]
  assert len(pay['operations'])==1
  if c['type']=='paymentout':
   ret=docs['salesreturn'][p.ident(pay['operations'][0],'salesreturn')]
   demand=docs['demand'][p.ident(ret['demand'],'demand')];returns=[ret]
  else:
   demand=docs['demand'][p.ident(pay['operations'][0],'demand')]
   returns=[docs['salesreturn'][p.ident(x,'salesreturn')] for x in demand.get('returns',[])]
  order=docs['customerorder'].get(p.ident(demand['customerOrder'],'customerorder')) if demand.get('customerOrder') else None
  rows.append({'payment_type':c['type'],'payment_id':pay['id'],'payment_name':pay['name'],'payment_sum_minor':pay['sum'],'linked_minor':pay['operations'][0]['linkedSum'],'demand_id':demand['id'],'demand_name':demand['name'],'demand_sum_minor':demand['sum'],'order_id':order['id'] if order else None,'order_sum_minor':order['sum'] if order else None,'returns':[{'id':d['id'],'name':d['name'],'sum_minor':d['sum'],'positions':len(r.rows(d)),'quantity':sum(x['quantity'] for x in r.rows(d)),'order_price_target_minor':float(sum(b.R(b.D(next((o for o in r.rows(order) if m.href(o['assortment'])==m.href(x['assortment'])),{}).get('price'))*b.D(x['quantity'])*(100-b.D(x.get('discount')))/100) for x in r.rows(d))) if order else None} for d in returns]})
 save(db,'result:v1',{'status':'complete','at':m.now(),'documents':docs,'rows':rows,'ms_writes':0})
 print('Deferred amount cases reviewed; private results saved; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Deferred review stopped; inspect private diagnostics.');sys.exit(1)
