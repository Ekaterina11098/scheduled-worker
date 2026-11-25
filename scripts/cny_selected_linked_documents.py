"""Convert only the explicitly authorized payment and receipt linked to one order."""
import copy,sys
from decimal import Decimal
import cny_single_document_test as s
b=s.b;m=s.m;ROOT=s.ROOT
def save(db,key,value):s.save(db,'linked:'+key,value)
def moneyshape(d):
 return {'sum':d.get('sum'),'rate':d.get('rate'),'positions':[(p['id'],p.get('quantity'),p.get('price')) for p in d.get('positions',{}).get('rows',[])]}
def verify_header(old,new):
 for key in ('id','name','moment','description','applicable','vatEnabled','vatIncluded','externalCode','paymentPurpose','noClosingDocs'):
  assert old.get(key)==new.get(key),'Header changed: '+key
 for key in ('agent','organization','store','state','contract','project','purchaseOrder','organizationAccount','agentAccount','expenseItem'):
  assert m.href(old.get(key,{}))==m.href(new.get(key,{})),'Reference changed: '+key
def verify_currency(d,cny):
 assert d['rate']['currency']['id']==cny['id'] and b.D(d['rate'].get('value',1))==12
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(ROOT+'linked_config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='selected_order_linked_payment_and_supply' and cfg['rub_per_cny']==12
 if db.get(ROOT+'linked:result:v1'):
  raise m.Stop('Result exists: reconcile saved result instead of rerunning mutations')
 paths={'order':'entity/purchaseorder/'+cfg['parent_id'],'payment':'entity/paymentout/'+cfg['payment_id'],'supply':'entity/supply/'+cfg['supply_id']}
 before={key:s.getdoc(t,path) for key,path in paths.items()}
 currencies=b.fullrows(t,'entity/currency');default=next(c for c in currencies if c.get('default'))
 assert default['isoCode']=='RUB'
 cny=[c for c in currencies if c.get('isoCode')=='CNY' and not c.get('archived')];assert len(cny)==1;cny=cny[0]
 order=before['order'];payment=before['payment'];supply=before['supply']
 verify_currency(order,cny)
 assert any(m.href(x).split('?')[0]==m.MS+paths['payment'] for x in order.get('payments',[]))
 assert any(m.href(x).split('?')[0]==m.MS+paths['supply'] for x in order.get('supplies',[]))
 assert m.href(supply['purchaseOrder'])==m.MS+paths['order']
 ops=payment.get('operations',[])
 assert len(ops)==1 and m.href(ops[0])==m.MS+paths['order'],'Payment has other allocations'
 assert b.D(ops[0]['linkedSum'])==b.D(payment['sum'])
 for doc in (payment,supply):
  assert doc['rate']['currency']['isoCode']=='RUB' and b.D(doc['rate'].get('value',1))==1
  assert b.D(doc['sum'])==b.D(order['sum'])*12
 if payment.get('organizationAccount'):
  account=t.request(m.MS,m.href(payment['organizationAccount'])[len(m.MS):],params={'expand':'currency'})
  assert not account.get('currency') or account['currency'].get('id') in (default['id'],cny['id']),'Account currency constraint'
 plan=b.plan(supply,supply['positions']['rows'])
 assert b.D(plan['actual_minor'])==b.D(order['sum']) and b.D(plan['deviation_minor'])==0
 paybody={'rate':{'currency':m.meta(cny),'value':12},'sum':int(b.R(b.D(payment['sum'])/12)),'operations':[]}
 if 'vatSum' in payment:paybody['vatSum']=int(b.R(b.D(payment['vatSum'])/12))
 for op in ops:paybody['operations'].append({**m.meta(op),'linkedSum':int(b.R(b.D(op['linkedSum'])/12))})
 assert sum(x['linkedSum'] for x in paybody['operations'])==paybody['sum']
 supplybody={'rate':{'currency':m.meta(cny),'value':12},'positions':[]}
 for old,price in zip(supply['positions']['rows'],plan['price_minor']):
  p={k:copy.deepcopy(old[k]) for k in ('id','quantity','discount','vat','vatEnabled','pack','slot','things','country','gtd','customsDeclarationNumber','trackingCodes') if k in old}
  p['assortment']=m.meta(old['assortment']);p['price']=int(price);supplybody['positions'].append(p)
 if isinstance(supply.get('overhead'),dict) and 'sum' in supply['overhead']:
  supplybody['overhead']={**supply['overhead'],'sum':int(b.R(b.D(supply['overhead']['sum'])/12))}
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'currency_before':currencies,'payment_body':paybody,'supply_body':supplybody,'plan':plan})
 for key,body in (('payment',paybody),('supply',supplybody)):
  fresh=s.getdoc(t,paths[key])
  assert b.digest(s.stable(fresh))==b.digest(s.stable(before[key])),'Source changed before '+key
  # The parent order's money and items must remain exactly as approved.
  assert moneyshape(s.getdoc(t,paths['order']))==moneyshape(order)
  s.NarrowWriter(db,paths[key]).write_once(paths[key],'PUT',body,'linked:'+key+'_intent:v1')
  after=s.getdoc(t,paths[key])
  save(db,key+'_readback:v1',{'at':m.now(),'after':after})
  verify_header(before[key],after);verify_currency(after,cny)
  assert b.D(after['sum'])==b.D(order['sum'])
  if key=='payment':
   assert b.D(after.get('vatSum'))==b.D(paybody.get('vatSum'))
   assert [(m.href(x),b.D(x['linkedSum'])) for x in after.get('operations',[])]==[(m.href(x),b.D(x['linkedSum'])) for x in paybody['operations']]
  else:
   aa=after['positions']['rows'];bb=supply['positions']['rows'];assert len(aa)==len(bb)
   for old,new,p in zip(bb,aa,supplybody['positions']):
    for field in ('id','quantity','discount','vat','vatEnabled','pack','slot','things','country','gtd'):
     assert old.get(field)==new.get(field),'Position changed: '+field
    assert m.href(old['assortment'])==m.href(new['assortment'])
    assert b.D(new['price'])==b.D(p['price'])
    assert b.D(new['price'])*12==b.D(old['price'])
 final={key:s.getdoc(t,path) for key,path in paths.items()}
 finalcurr=b.fullrows(t,'entity/currency')
 assert next(c for c in finalcurr if c.get('default'))['id']==default['id']
 assert next(c for c in finalcurr if c.get('default'))['isoCode']=='RUB'
 assert moneyshape(final['order'])==moneyshape(order)
 assert all(b.D(d['sum'])==b.D(order['sum']) for d in final.values())
 assert b.D(final['order']['payedSum'])==b.D(order['sum'])
 assert b.D(final['order']['shippedSum'])==b.D(order['sum'])
 assert sum(b.D(x['linkedSum']) for x in final['payment']['operations'])==b.D(order['sum'])
 assert m.href(final['supply']['purchaseOrder'])==m.MS+paths['order']
 assert any(m.href(x).split('?')[0]==m.MS+paths['payment'] for x in final['order']['payments'])
 assert any(m.href(x).split('?')[0]==m.MS+paths['supply'] for x in final['order']['supplies'])
 save(db,'final_readback:v1',{'at':m.now(),'documents':final,'currencies':finalcurr})
 save(db,'result:v1',{'status':'verified','at':m.now(),'accounting_currency':'RUB','rate':12,'documents':[{ 'type':d['meta']['type'],'id':d['id'],'name':d['name'],'currency':d['rate']['currency']['isoCode'],'sum_minor':d['sum'],'payedSum':d.get('payedSum'),'shippedSum':d.get('shippedSum'),'vatSum':d.get('vatSum')} for d in final.values()],'positions':len(final['supply']['positions']['rows']),'quantity':str(sum((b.D(p['quantity']) for p in final['supply']['positions']['rows']),Decimal(0))),'deviation_minor':plan['deviation_minor'],'links_preserved':True,'order_prices_unchanged':True})
 print('Authorized linked payment and receipt converted and reconciled privately.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'error':type(error).__name__,'detail':str(error)})
  except Exception:pass
  print('Linked-document conversion stopped; inspect private diagnostics before retry.')
  sys.exit(1)
