"""Align one explicitly authorized chain to its current order amount; no bulk."""
import copy,sys
import cny_single_document_test as s
import cny_document_rollout as r
b=s.b;m=s.m
P='selected_chain_align:'
def save(db,k,v):b.put(db,P+k,v)
def shape(d):
 return [[p['id'],r.number(p['quantity']),m.href(p['assortment']),r.number(p.get('discount')),r.number(p.get('vat')),p.get('vatEnabled')] for p in r.rows(d)]
def invariants(old,new):
 assert shape(old)==shape(new),'Position structure changed'
 for k in ('id','name','moment','description','applicable','externalCode','vatEnabled','vatIncluded'):
  assert old.get(k)==new.get(k),'Header changed: '+k
 for k in ('demand','customerOrder','agent','organization','store','contract','project','state','organizationAccount','agentAccount'):
  assert m.href(old.get(k,{}))==m.href(new.get(k,{})),'Reference changed: '+k
 for k in ('returns','payments','demands','losses'):
  assert [m.href(x) for x in old.get(k,[])]==[m.href(x) for x in new.get(k,[])],'Related list changed'
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_chain_match_current_order'
 assert cfg['preserve_quantities'] and cfg['preserve_position_order'] and cfg['preserve_links']
 assert cfg['max_changed_documents']==3 and not cfg['bulk_allowed']
 assert not db.get(r.ROOT+'authorization:v1')['authorized']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt: reconcile before replay'
 items=db.get(cfg['source_config_key'])['documents']
 assert {x['type'] for x in items}=={'customerorder','demand','salesreturn','paymentin'} and len(items)==4
 paths={x['type']:'entity/'+x['type']+'/'+x['id'] for x in items}
 def read():return {k:s.getdoc(t,p) for k,p in paths.items()}
 before=read();order=before['customerorder'];target=int(order['sum'])
 assert target==cfg['expected_order_sum_minor'] and target>0
 for typ,d in before.items():
  assert b.D(d['sum'])==cfg['expected_before'][typ],'Amount changed since authorization'
  assert d['rate']['currency']['isoCode']=='CNY'
  if typ!='paymentin':
   assert len(r.rows(d))==1 and b.D(r.rows(d)[0]['quantity'])==1
   assert b.D(r.rows(d)[0].get('discount'))==0 and not d.get('vatEnabled')
 assert len({m.href(r.rows(before[k])[0]['assortment']) for k in ('customerorder','demand','salesreturn')})==1
 assert m.href(before['demand']['customerOrder'])==m.MS+paths['customerorder']
 assert m.href(before['salesreturn']['demand'])==m.MS+paths['demand']
 assert [m.href(x) for x in before['demand'].get('returns',[])]==[m.MS+paths['salesreturn']]
 ops=before['paymentin'].get('operations',[])
 assert len(ops)==1 and m.href(ops[0])==m.MS+paths['demand']
 assert [m.href(x) for x in before['demand'].get('payments',[])]==[m.MS+paths['paymentin']]
 bodies={}
 for typ in ('demand','salesreturn'):
  old=r.rows(before[typ])[0]
  p={k:copy.deepcopy(old[k]) for k in r.FIELDS if k in old}
  p['assortment']=m.meta(old['assortment']);p['price']=target
  bodies[typ]={'positions':[p]}
 bodies['paymentin']={'sum':target,'operations':[{**m.meta(ops[0]),'linkedSum':target}]}
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'bodies':bodies,'target_minor':target})
 expected=before.copy()
 for typ in ('demand','salesreturn','paymentin'):
  fresh=read()
  for k in before:
   invariants(before[k],fresh[k])
   assert r.signature(fresh[k],k)==r.signature(expected[k],k),'Concurrent monetary change'
  s.NarrowWriter(db,paths[typ]).write_once(paths[typ],'PUT',bodies[typ],P+typ+':intent:v1')
  after=read()
  save(db,'readback:'+typ+':v1',{'at':m.now(),'documents':after})
  for k in before:invariants(before[k],after[k])
  assert r.signature(after['customerorder'],'customerorder')==r.signature(order,'customerorder'),'Order changed'
  if b.D(after[typ]['sum'])!=target:
   save(db,'result:v1',{'status':'stopped','failed_type':typ,'at':m.now(),'target_minor':target,'documents':after,'response':db.get(s.ROOT+P+typ+':intent:v1:response')})
   raise m.Stop('Target not saved; stop and reconcile private readback')
  if typ!='paymentin':assert b.D(r.rows(after[typ])[0]['price'])==target
  else:assert b.D(after[typ]['operations'][0]['linkedSum'])==target
  expected=after
  save(db,'progress:v1',{'status':'running','last_verified':typ,'at':m.now()})
 final=read()
 for typ,d in final.items():
  invariants(before[typ],d)
  assert b.D(d['sum'])==target and d['rate']['currency']['isoCode']=='CNY'
 assert b.D(final['paymentin']['operations'][0]['linkedSum'])==target
 save(db,'result:v1',{'status':'verified','at':m.now(),'target_minor':target,'documents':final,'summary':[{'type':k,'id':d['id'],'name':d['name'],'before_minor':before[k]['sum'],'after_minor':d['sum'],'currency':'CNY','rate':d['rate'].get('value',1),'currency_id':d['rate']['currency']['id'],'positions':len(r.rows(d)),'quantity':sum(p['quantity'] for p in r.rows(d))} for k,d in final.items()],'quantities_order_and_links_preserved':True,'bulk_enabled':False})
 print('One selected chain verified; private result saved. Bulk remains disabled.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error)})
  except Exception:pass
  print('Selected-chain operation stopped; inspect private diagnostics.');sys.exit(1)
