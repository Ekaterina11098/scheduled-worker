"""Fresh read-only currency-reference inventory, with private stock and header checkpoints."""
import collections,concurrent.futures,sys,traceback
import cny_incoming_refs_apply as h
r=h.r;b=h.b;m=h.m
P='all_remaining_refs_20261127:'
def save(db,k,v):b.put(db,P+k,v)
def scan(typ):
 t=b.ReadOnly();db=m.Cache(t);cc=db.get(b.ROOT+P+'start:v1')['currencies']
 base=next(c for c in cc if c.get('default'));iso={m.href(c):c.get('isoCode') for c in cc}
 ids=[];candidates=[];issues=[];rates=collections.Counter();offset=0;count=None;amount=b.D(0)
 while True:
  page=t.request(m.MS,'entity/'+typ,params={'limit':1000,'offset':offset,'order':'id,asc'})
  if count is None:count=page['meta']['size']
  assert page['meta']['size']==count,'Document count changed during preflight'
  rows=page['rows'];ids.extend(x['id'] for x in rows)
  for d in rows:
   amount+=b.D(d.get('sum'));rate=d.get('rate');cur=r.currency(d) if rate else ''
   value=b.D(rate.get('value',1)) if rate else b.D(1)
   rates[(iso.get(cur,'implicit'),str(value),cur==m.href(base))]+=1
   if rate and (cur!=m.href(base) or value!=1):
    if iso.get(cur)=='CNY' and value in (1,12):candidates.append(d['id'])
    else:issues.append({'id':d['id'],'currency':cur,'rate':str(value),'reason':'Unexpected currency or rate'})
  save(db,'headers:'+typ+':'+str(offset),{'at':m.now(),'documents':rows})
  save(db,'progress:'+typ,{'at':m.now(),'checked':len(ids),'total':count,'candidates':len(candidates)})
  if len(ids)==count:break
  assert rows;offset+=len(rows)
 assert len(set(ids))==len(ids)
 out={'status':'complete','at':m.now(),'type':typ,'count':count,'ids':ids,'candidates':candidates,'issues':issues,'nominal_sum_minor':str(amount),'rates':[{'iso':k[0],'rate':k[1],'base':k[2],'count':v} for k,v in rates.items()]}
 save(db,'type:'+typ,out);return {k:v for k,v in out.items() if k not in ('ids','candidates','issues')}|{'candidates':len(candidates),'issues':len(issues)}
def main():
 t=b.ReadOnly();db=m.Cache(t)
 assert not db.get(b.ROOT+P+'preflight:v1'),'Existing preflight; do not overwrite'
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 wh=h.warehouse(t);mf=db.get(b.ROOT+'backup_manifest:v1')
 types=[x['type'] for x in mf['counts']]+['inventory']
 assert len(types)==len(set(types))
 save(db,'start:v1',{'at':m.now(),'currencies':cc,'base':base,'warehouse_quantities':wh,'types':types,'ms_writes':0})
 result=[];errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  jobs={pool.submit(scan,typ):typ for typ in types}
  for f in concurrent.futures.as_completed(jobs):
   try:result.append(f.result())
   except Exception as e:errors.append({'type':jobs[f],'reason':str(e)})
   save(db,'progress:v1',{'at':m.now(),'types_complete':len(result),'types_total':len(types),'errors':errors,'ms_writes':0})
 wh1=h.warehouse(t)
 save(db,'preflight:v1',{'status':'complete' if not errors else 'incomplete','at':m.now(),'types':result,'errors':errors,'warehouse_quantities_unchanged':wh1==wh,'warehouse_quantities_after':wh1,'ms_writes':0})
 assert not errors and wh1==wh,'Preflight errors or concurrent stock changes'
 print('Private current reference inventory complete; MS unchanged.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:preflight:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Preflight stopped; private diagnostic saved.');sys.exit(1)
