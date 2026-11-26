"""Align one selected partial-return chain using order prices, preserving structure."""
import copy,sys,traceback
import cny_one_chain_align_test as a
s=a.s;r=a.r;b=a.b;m=a.m
P='partial_return_chain_align:'
def save(db,k,v):b.put(db,P+k,v)
def check(old,new):
 a.invariants(old,new)
 assert m.href(old['rate']['currency'])==m.href(new['rate']['currency']),'Currency reference changed'
 assert b.D(old['rate'].get('value',1))==b.D(new['rate'].get('value',1)),'Rate changed'
 if 'operations' in old:assert [m.href(x) for x in old['operations']]==[m.href(x) for x in new.get('operations',[])],'Payment links changed'
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_partial_return_chain_order_prices'
 assert cfg['max_changed_documents']==4 and not cfg['bulk_allowed']
 assert all(cfg[k] for k in ('preserve_quantities','preserve_position_order','preserve_links'))
 assert not db.get(r.ROOT+'authorization:v1')['authorized']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing snapshot requires reconciliation; no replay'
 items=cfg['documents'];assert len(items)==5 and {x['type'] for x in items}=={'customerorder','demand','salesreturn','paymentin','paymentout'}
 paths={x['type']:'entity/'+x['type']+'/'+x['id'] for x in items}
 def read():return {k:s.getdoc(t,p) for k,p in paths.items()}
 before=read();save(db,'inspection:v1',{'at':m.now(),'documents':before})
 originals={}
 for item in items:
  typ=item['type'];d=before[typ]
  page=db.get(b.ROOT+'backup:'+typ+':page:'+str(item['baseline_offset']))
  assert b.digest(page['documents'])==page['sha256']
  old=next(x for x in page['documents'] if x['id']==item['id']);originals[typ]=old
  assert a.shape(old)==a.shape(d),'Position shape changed since source backup'
  assert b.D(d['sum'])==cfg['expected_before'][typ],'Current amount changed'
  assert d['rate']['currency']['isoCode']=='CNY'
  for k in ('demand','customerOrder','agent','organization','store'):assert m.href(d.get(k,{}))==m.href(old.get(k,{}))
 for typ,count in (('customerorder',2),('demand',2),('salesreturn',1)):
  pp=r.rows(before[typ]);assert len(pp)==count
  assert all(b.D(p['quantity'])==1 and b.D(p.get('discount'))==0 and b.D(p.get('vat'))==0 for p in pp)
 order=before['customerorder'];full=cfg['full_target_minor'];partial=cfg['return_target_minor'];prices=cfg['order_price_minor']
 assert b.D(order['sum'])==full and [b.D(p['price']) for p in r.rows(order)]==prices and sum(prices)==full
 price_by_product={m.href(p['assortment']):int(p['price']) for p in r.rows(order)}
 assert len(price_by_product)==2
 assert [m.href(p['assortment']) for p in r.rows(before['demand'])]==list(price_by_product)
 returned=m.href(r.rows(before['salesreturn'])[0]['assortment'])
 assert returned in price_by_product and price_by_product[returned]==partial
 assert m.href(before['demand']['customerOrder'])==m.MS+paths['customerorder']
 assert m.href(before['salesreturn']['demand'])==m.MS+paths['demand']
 assert [m.href(x) for x in before['demand'].get('returns',[])]==[m.MS+paths['salesreturn']]
 assert [m.href(x) for x in before['demand'].get('payments',[])]==[m.MS+paths['paymentin']]
 assert [m.href(x) for x in before['salesreturn'].get('payments',[])]==[m.MS+paths['paymentout']]
 assert not order.get('payments')
 for typ,basis in (('paymentin','demand'),('paymentout','salesreturn')):
  ops=before[typ].get('operations',[])
  assert len(ops)==1 and m.href(ops[0])==m.MS+paths[basis],'Payment allocates to another document'
  assert b.D(ops[0]['linkedSum'])==b.D(before[typ]['sum'])
 goals={'customerorder':full,'demand':full,'paymentin':full,'salesreturn':partial,'paymentout':partial}
 bodies={}
 for typ in ('demand','salesreturn'):
  pp=[]
  for old in r.rows(before[typ]):
   p={k:copy.deepcopy(old[k]) for k in r.FIELDS if k in old}
   p['assortment']=m.meta(old['assortment']);p['price']=price_by_product[m.href(old['assortment'])];pp.append(p)
  bodies[typ]={'positions':pp}
 for typ in ('paymentin','paymentout'):
  assert b.D(before[typ].get('vatSum'))==0
  bodies[typ]={'sum':goals[typ],'operations':[{**m.meta(before[typ]['operations'][0]),'linkedSum':goals[typ]}]}
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'originals':originals,'bodies':bodies,'goals_minor':goals})
 expected=before
 for typ in ('demand','salesreturn','paymentin','paymentout'):
  fresh=read()
  for k in before:
   check(before[k],fresh[k])
   assert r.signature(fresh[k],k)==r.signature(expected[k],k),'Concurrent monetary edit'
  s.NarrowWriter(db,paths[typ]).write_once(paths[typ],'PUT',bodies[typ],P+typ+':intent:v1')
  after=read();save(db,'readback:'+typ+':v1',{'at':m.now(),'documents':after})
  for k in before:check(before[k],after[k])
  if b.D(after[typ]['sum'])!=goals[typ]:
   save(db,'result:v1',{'status':'stopped','failed_type':typ,'at':m.now(),'documents':after,'response':db.get(s.ROOT+P+typ+':intent:v1:response')})
   raise m.Stop('Target not observed; no more writes')
  if typ in ('demand','salesreturn'):
   assert [b.D(p['price']) for p in r.rows(after[typ])]==[price_by_product[m.href(p['assortment'])] for p in r.rows(after[typ])]
  else:assert b.D(after[typ]['operations'][0]['linkedSum'])==goals[typ]
  for k in before:
   if k!=typ:assert r.signature(after[k],k)==r.signature(expected[k],k),'Other monetary change'
  expected=after
  save(db,'progress:v1',{'status':'running','last_verified':typ,'at':m.now()})
 final=read()
 for typ,d in final.items():
  check(before[typ],d)
  assert b.D(d['sum'])==goals[typ] and r.signature(d,typ)==r.signature(expected[typ],typ)
 assert r.signature(final['customerorder'],'customerorder')==r.signature(order,'customerorder')
 save(db,'result:v1',{'status':'verified','at':m.now(),'documents':final,'summary':[{'type':k,'id':d['id'],'name':d['name'],'before_minor':before[k]['sum'],'after_minor':d['sum'],'prices_minor':[p['price'] for p in r.rows(d)],'positions':len(r.rows(d)),'quantity':sum(p['quantity'] for p in r.rows(d)),'currency':d['rate']['currency']['isoCode'],'rate':d['rate'].get('value',1),'currency_id':d['rate']['currency']['id']} for k,d in final.items()],'order_unchanged':True,'quantities_order_links_preserved':True,'bulk_enabled':False})
 print('Selected partial-return chain verified; private results saved. Bulk disabled.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected partial-return operation stopped; inspect private diagnostics.');sys.exit(1)
