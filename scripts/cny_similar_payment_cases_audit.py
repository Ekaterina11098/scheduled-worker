"""Read-only current audit of payments found by complete returns inventory."""
import collections,sys,traceback
import cny_document_rollout as r
b=r.b;m=b.m;P='similar_payment_cases_audit:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['mode']=='read_only'
 currencies=b.fullrows(t,'entity/currency');cm={m.href(c):c for c in currencies}
 count=t.request(m.MS,'entity/salesreturn',params={'limit':1})['meta']['size']
 payments={};basis_ids=collections.defaultdict(set)
 for typ,ids in cfg['payments'].items():
  payments[typ]={}
  for offset in range(0,len(ids),100):
   dd=r.live(t,typ,ids[offset:offset+100]);payments[typ].update(dd)
   save(db,'payments:'+typ+':'+str(offset),{'at':m.now(),'documents':list(dd.values())})
   for d in dd.values():
    for o in d.get('operations',[]):
     href=m.href(o).split('?')[0];assert href.startswith(m.MS+'entity/')
     bt,bi=href[len(m.MS+'entity/'):].split('/')
     assert bt in ('demand','salesreturn','customerorder')
     basis_ids[bt].add(bi)
   save(db,'progress:v1',{'at':m.now(),'phase':'payments','checked':sum(len(v) for v in payments.values()),'ms_writes':0})
 basis={}
 for typ,ss in basis_ids.items():
  ids=sorted(ss);basis[typ]={}
  for offset in range(0,len(ids),100):
   dd=r.live(t,typ,ids[offset:offset+100]);basis[typ].update(dd)
   save(db,'basis:'+typ+':'+str(offset),{'at':m.now(),'documents':list(dd.values())})
   save(db,'progress:v1',{'at':m.now(),'phase':'basis','checked':sum(len(v) for v in basis.values()),'ms_writes':0})
 records=[];counts=collections.Counter();by_type={}
 for typ,dd in payments.items():
  tc=collections.Counter()
  for d in dd.values():
   ops=d.get('operations',[]);allocated=sum((b.D(o.get('linkedSum')) for o in ops),b.D(0))
   partial=allocated<b.D(d['sum']);over=allocated>b.D(d['sum'])
   if partial:tc['partial_allocation']+=1
   if over:tc['over_allocation']+=1
   if len(ops)!=1:tc['multiple_or_missing_basis']+=1
   links=[]
   for o in ops:
    bt,bi=m.href(o).split('?')[0][len(m.MS+'entity/'):].split('/')
    bd=basis[bt][bi]
    pc=cm[r.currency(d)];bc=cm[r.currency(bd)]
    mismatch=r.currency(d)!=r.currency(bd) or b.D(d['rate'].get('value',1))!=b.D(bd['rate'].get('value',1))
    nominal=b.D(d['sum'])!=b.D(bd['sum']) if len(ops)==1 else None
    links.append({'basis_type':bt,'basis_id':bi,'basis_name':bd['name'],'basis_moment':bd['moment'],'basis_sum_minor':bd['sum'],'basis_payed_minor':bd.get('payedSum'),'basis_currency_id':bc['id'],'basis_iso':bc['isoCode'],'basis_rate':bd['rate'].get('value',1),'linked_minor':o.get('linkedSum'),'currency_or_rate_mismatch':mismatch,'nominal_sum_mismatch':nominal})
   if any(x['currency_or_rate_mismatch'] for x in links):tc['currency_or_rate_mismatch']+=1
   if any(x['nominal_sum_mismatch'] for x in links):tc['nominal_sum_mismatch']+=1
   tc['checked']+=1
   records.append({'type':typ,'id':d['id'],'name':d['name'],'moment':d['moment'],'sum_minor':d['sum'],'currency_id':cm[r.currency(d)]['id'],'iso':cm[r.currency(d)]['isoCode'],'rate':d['rate'].get('value',1),'allocated_minor':float(allocated),'unallocated_minor':float(b.D(d['sum'])-allocated),'partial_allocation':partial,'over_allocation':over,'links':links})
  by_type[typ]=dict(tc);counts.update(tc)
 for i in range(0,len(records),100):save(db,'records:'+str(i),{'at':m.now(),'rows':records[i:i+100]})
 save(db,'result:v1',{'status':'complete','at':m.now(),'counts':dict(counts),'by_type':by_type,'returns_count_now':count,'returns_count_at_source':cfg['expected_returns'],'basis_counts':{k:len(v) for k,v in basis.items()},'scope':'Payments linked in previous complete returns inventory; current payment and basis readback','ms_writes':0})
 print('Read-only related-payment audit complete; private results saved; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only payment audit stopped; inspect private diagnostics.');sys.exit(1)
