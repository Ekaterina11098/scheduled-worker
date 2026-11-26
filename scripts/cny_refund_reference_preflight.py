"""Preflight approved equal-nominal refund currency references. MS GET only."""
import collections,copy,sys,traceback
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='refund_currency_reference_normalize:'
TYPES=('customerorder','demand','salesreturn','paymentin','paymentout')
def save(db,k,v):b.put(db,P+k,v)
def readids(t,db,typ,ids):
 out={};ids=sorted(set(ids))
 for i in range(0,len(ids),50):
  dd=r.live(t,typ,ids[i:i+50]);out.update(dd)
  save(db,'inspection:'+typ+':'+str(i),{'at':m.now(),'documents':dd})
 return out
def ident(ref,typ):
 href=m.href(ref).split('?')[0];prefix=m.MS+'entity/'+typ+'/'
 assert href.startswith(prefix),'Unexpected reference type'
 return href[len(prefix):]
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['mode']=='inspect' and cfg['scope']=='approved_same_nominal_refund_chains_to_base_cny'
 assert cfg['expected_cases']==156 and len(cfg['cases'])==156 and cfg['preserve_all_nominal_sums'] and cfg['preserve_positions'] and not cfg['outside_ms_changes']
 docs={}
 docs['salesreturn']=readids(t,db,'salesreturn',[c['links'][0]['basis_id'] for c in cfg['cases']])
 docs['paymentout']=readids(t,db,'paymentout',[c['id'] for c in cfg['cases']])
 docs['demand']=readids(t,db,'demand',[ident(d['demand'],'demand') for d in docs['salesreturn'].values()])
 docs['customerorder']=readids(t,db,'customerorder',[ident(d['customerOrder'],'customerorder') for d in docs['demand'].values() if d.get('customerOrder')])
 docs['paymentin']=readids(t,db,'paymentin',[ident(p,'paymentin') for d in docs['demand'].values() for p in d.get('payments',[])])
 currencies=b.fullrows(t,'entity/currency');cm={m.href(c):c for c in currencies};base=next(c for c in currencies if c.get('default'))
 assert base['id']==cfg['base_currency_id'] and base['isoCode']=='CNY' and b.D(base['rate'])==1
 safe=[];conflicts=[]
 for c in cfg['cases']:
  try:
   po=docs['paymentout'][c['id']];ret=docs['salesreturn'][c['links'][0]['basis_id']]
   demand=docs['demand'][ident(ret['demand'],'demand')]
   order=docs['customerorder'][ident(demand['customerOrder'],'customerorder')]
   chain={'customerorder':order,'demand':demand,'salesreturn':ret,'paymentout':po}
   if demand.get('payments'):
    assert len(demand['payments'])==1
    chain['paymentin']=docs['paymentin'][ident(demand['payments'][0],'paymentin')]
   target=b.D(ret['sum'])
   assert target==b.D(c['sum_minor']) and target==b.D(c['links'][0]['basis_sum_minor'])
   assert [ident(x,'salesreturn') for x in demand.get('returns',[])]==[ret['id']],'Shared return basis'
   assert not order.get('payments'),'Direct order payment requires review'
   assert [ident(x,'paymentout') for x in ret.get('payments',[])]==[po['id']]
   for typ,d in chain.items():
    assert b.D(d['sum'])==target,'Nominal amounts differ in chain'
    assert cm[r.currency(d)]['isoCode']=='CNY' and b.D(d['rate'].get('value',1)) in (1,12)
    if typ in ('paymentin','paymentout'):
     basis='demand' if typ=='paymentin' else 'salesreturn'
     assert len(d['operations'])==1 and ident(d['operations'][0],basis)==chain[basis]['id']
     assert b.D(d['operations'][0]['linkedSum'])==target and b.D(d.get('vatSum'))==0
   safe.append({'return_id':ret['id'],'before':chain})
  except Exception as e:conflicts.append({'paymentout_id':c['id'],'name':c['name'],'detail':str(e)})
 seen=collections.defaultdict(set)
 for chain in safe:
  for typ,d in chain['before'].items():
   assert d['id'] not in seen[typ],'Shared document in selected chains';seen[typ].add(d['id'])
 for i in range(0,len(safe),20):save(db,'sources:'+str(i//20),{'chains':safe[i:i+20],'at':m.now()})
 save(db,'preflight:v1',{'status':'complete' if not conflicts else 'review_required','safe_cases':len(safe),'source_groups':(len(safe)+19)//20,'conflicts':conflicts,'currencies':currencies,'documents':{k:len(v) for k,v in seen.items()},'at':m.now(),'ms_writes':0})
 print('Selected-chain preflight complete; private results saved; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:inspect:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Preflight stopped; inspect private diagnostics; MS writes zero.');sys.exit(1)
