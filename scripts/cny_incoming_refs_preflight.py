"""Read-only complete incoming currency-reference audit and private snapshots."""
import copy,sys,traceback
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='incoming_cost_refs_all:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'authorization:v1');assert cfg['authorized'] and cfg['preserve_quantities']
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 save(db,'currencies_before:v1',{'rows':cc,'at':m.now()})
 for label,path,params in [('warehouses','report/stock/bystore',{'filter':'stockMode=all'}),('costs','report/stock/all',{'filter':'stockMode=all;quantityMode=all'})]:
  rr=b.fullrows(t,path,params)
  for o in range(0,len(rr),100):save(db,'before:'+label+':'+str(o),{'rows':rr[o:o+100],'at':m.now()})
  save(db,'before:'+label+':manifest',{'count':len(rr),'pages':list(range(0,len(rr),100))})
 manifest=db.get(b.ROOT+'backup_manifest:v1');summary={};issues=[]
 for typ in ('supply','enter'):
  originals={}
  count=next(x['count'] for x in manifest['counts'] if x['type']==typ)
  for o in range(0,count,100):
   p=db.get(b.ROOT+'backup:'+typ+':page:'+str(o));assert b.digest(p['documents'])==p['sha256']
   originals.update({d['id']:d for d in p['documents']})
  heads=b.fullrows(t,'entity/'+typ);ids=[d['id'] for d in heads];ready=[];already=[];stats={'total':len(ids),'positions':0,'payments':0,'overheads':0}
  for o in range(0,len(ids),50):
   docs=r.live(t,typ,ids[o:o+50]);save(db,'preflight:'+typ+':'+str(o),{'documents':docs,'at':m.now()})
   for i,d in docs.items():
    try:
     assert i in originals,'Not in original conversion backup'
     old=originals[i];a.invariants(old,d)
     body,goal,plan=r.prepare(old,typ,d['rate']['currency'])
     sig=r.signature(d,typ)
     if r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1:
      goal['rate']='1';assert sig==goal,'Already-base prices differ from historical conversion';already.append(i);continue
     assert d['rate']['currency']['meta']['type']=='currency'
     assert next(c['isoCode'] for c in cc if m.href(c)==r.currency(d))=='CNY'
     assert b.D(d['rate'].get('value',1))==12,'Unexpected document rate'
     assert sig==goal,'Prices differ from original verified conversion'
     assert len(r.rows(d))<=1000
     assert all(b.D(p['price'])==int(p['price']) for p in r.rows(d)),'Fractional minor unit'
     assert all(p['assortment']['meta']['type'] in ('product','bundle','variant','service') for p in r.rows(d))
     ready.append(i);stats['positions']+=len(r.rows(d));stats['payments']+=len(d.get('payments',[]));stats['overheads']+=bool(d.get('overhead',{}).get('sum'))
    except Exception as e:issues.append({'type':typ,'id':i,'name':d.get('name'),'detail':str(e)})
   save(db,'progress:v1',{'status':'preflight','type':typ,'checked':min(o+50,len(ids)),'total':len(ids),'issues':len(issues),'at':m.now()})
  summary[typ]={**stats,'ready':ready,'already':already,'pages':list(range(0,len(ids),50))}
 save(db,'preflight:v1',{'status':'complete','at':m.now(),'summary':summary,'issues':issues,'base':base,'ms_writes':0})
 print('Incoming currency audit complete; private snapshots saved; no MS writes.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:preflight:v1',{'detail':str(e),'trace':traceback.format_exc(),'at':m.now()})
  except Exception:pass
  print('Audit stopped; inspect private diagnostics.');sys.exit(1)
