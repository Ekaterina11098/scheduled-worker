"""Two explicitly selected product documents; preserve all rows and links."""
import copy,sys,traceback
import cny_one_chain_align_test as a
s=a.s;r=a.r;b=a.b;m=a.m
P='second_two_line_return_align:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='selected_two_line_demand_return_only'
 assert cfg['max_documents']==2 and not cfg['bulk_allowed']
 assert all(cfg[k] for k in ('preserve_quantities','preserve_position_order','preserve_links'))
 assert not db.get(r.ROOT+'authorization:v1')['authorized']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Previous intent exists; readback reconciliation required'
 items=cfg['documents'];assert len(items)==3 and {x['type'] for x in items}=={'customerorder','demand','salesreturn'}
 paths={x['type']:'entity/'+x['type']+'/'+x['id'] for x in items}
 def read():return {k:s.getdoc(t,p) for k,p in paths.items()}
 before=read();save(db,'inspection:v1',{'at':m.now(),'documents':before})
 target=cfg['target_minor'];prices=[int(p['price']) for p in r.rows(before['customerorder'])]
 assert all(b.D(p['price'])==price for p,price in zip(r.rows(before['customerorder']),prices))
 assert sum(prices)==target and len(prices)==2
 originals={}
 for item in items:
  typ=item['type'];d=before[typ]
  page=db.get(b.ROOT+'backup:'+typ+':page:'+str(item['baseline_offset']))
  assert b.digest(page['documents'])==page['sha256']
  old=next(x for x in page['documents'] if x['id']==item['id']);originals[typ]=old
  assert a.shape(d)==a.shape(old),'Quantity, order, assortment or tax fields changed from baseline'
  assert b.D(d['sum'])==cfg['expected_before'][typ],'Current amount changed'
  assert len(r.rows(d))==2 and all(b.D(p['quantity'])==1 and b.D(p.get('discount'))==0 and b.D(p.get('vat'))==0 for p in r.rows(d))
  assert d['rate']['currency']['isoCode']=='CNY'
 assert b.D(before['customerorder']['sum'])==target
 assert [b.D(p['price']) for p in r.rows(before['customerorder'])]==prices
 assortments=[m.href(p['assortment']) for p in r.rows(before['customerorder'])]
 assert len(set(assortments))==2
 for k in ('demand','salesreturn'):assert [m.href(p['assortment']) for p in r.rows(before[k])]==assortments
 assert m.href(before['demand']['customerOrder'])==m.MS+paths['customerorder']
 assert m.href(before['salesreturn']['demand'])==m.MS+paths['demand']
 assert [m.href(x) for x in before['demand'].get('returns',[])]==[m.MS+paths['salesreturn']]
 assert not before['demand'].get('payments') and not before['customerorder'].get('payments'),'New payment link requires review'
 bodies={}
 for typ in ('demand','salesreturn'):
  pp=[]
  for old,price in zip(r.rows(before[typ]),prices):
   p={k:copy.deepcopy(old[k]) for k in r.FIELDS if k in old}
   p['assortment']=m.meta(old['assortment']);p['price']=price;pp.append(p)
  bodies[typ]={'positions':pp}
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'originals':originals,'bodies':bodies,'target_minor':target})
 expected=before
 for typ in ('demand','salesreturn'):
  fresh=read()
  for k in before:
   a.invariants(before[k],fresh[k])
   assert r.signature(fresh[k],k)==r.signature(expected[k],k),'Concurrent monetary change'
  s.NarrowWriter(db,paths[typ]).write_once(paths[typ],'PUT',bodies[typ],P+typ+':intent:v1')
  after=read();save(db,'readback:'+typ+':v1',{'at':m.now(),'documents':after})
  for k in before:
   a.invariants(before[k],after[k])
   assert m.href(before[k]['rate']['currency'])==m.href(after[k]['rate']['currency'])
   assert b.D(before[k]['rate'].get('value',1))==b.D(after[k]['rate'].get('value',1))
  assert r.signature(after['customerorder'],'customerorder')==r.signature(before['customerorder'],'customerorder')
  if b.D(after[typ]['sum'])!=target or [b.D(p['price']) for p in r.rows(after[typ])]!=prices:
   save(db,'result:v1',{'status':'stopped','failed_type':typ,'at':m.now(),'documents':after,'response':db.get(s.ROOT+P+typ+':intent:v1:response')})
   raise m.Stop('Saved values do not match target; no further writes')
  for k in before:
   if k!=typ:assert r.signature(after[k],k)==r.signature(expected[k],k),'Other monetary fields changed'
  expected=after
  save(db,'progress:v1',{'status':'running','last_verified':typ,'at':m.now()})
 final=read()
 for typ,d in final.items():
  a.invariants(before[typ],d)
  assert b.D(d['sum'])==target and [b.D(p['price']) for p in r.rows(d)]==prices
  assert r.signature(d,typ)==r.signature(expected[typ],typ)
 save(db,'result:v1',{'status':'verified','at':m.now(),'target_minor':target,'documents':final,'summary':[{'type':k,'id':d['id'],'name':d['name'],'before_minor':before[k]['sum'],'after_minor':d['sum'],'prices_minor':[p['price'] for p in r.rows(d)],'positions':len(r.rows(d)),'quantity':sum(p['quantity'] for p in r.rows(d)),'currency':d['rate']['currency']['isoCode'],'currency_id':d['rate']['currency']['id'],'rate':d['rate'].get('value',1)} for k,d in final.items()],'preserved_quantities_order_links':True,'order_unchanged':True,'bulk_enabled':False})
 print('Selected pair verified; private result saved. No bulk changes.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected-pair operation stopped; inspect private diagnostics.');sys.exit(1)
