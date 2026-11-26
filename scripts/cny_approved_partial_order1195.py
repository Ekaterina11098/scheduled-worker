"""Correct one approved partial chain and inspect refund-payment availability."""
import copy,sys,traceback
import cny_approved_two_units_chain as z
r=z.r;b=z.b;m=z.m
P='approved_partial_order1195:';TYPES=('customerorder','demand','salesreturn','paymentin')
z.P=P;z.TYPES=TYPES
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_approved_partial_chain_three_sale_two_return'
 assert cfg['sale_minor']==119558 and cfg['refund_minor']==77891 and not cfg['bulk_allowed'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt; reconcile before retry'
 before=z.read(t,cfg);cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['id']==cfg['base_currency_id'] and base['isoCode']=='CNY' and b.D(base['rate'])==1
 for typ,d in before.items():
  z.invariant(cfg['before'][typ],d)
  assert z.same(cfg['before'][typ],d,typ),'Changed since reviewed snapshot'
 for typ in ('customerorder','demand','salesreturn'):
  assert len(r.rows(before[typ]))==(2 if typ=='salesreturn' else 3)
  assert all(b.D(p['quantity'])==1 and b.D(p.get('discount'))==0 and b.D(p.get('vat'))==0 for p in r.rows(before[typ]))
 order=before['customerorder'];demand=before['demand'];ret=before['salesreturn'];pay=before['paymentin']
 assert b.D(order['sum'])==cfg['sale_minor']
 price_map={m.href(p['assortment']):p['price'] for p in r.rows(order)};assert len(price_map)==3
 assert sum(b.D(price_map[m.href(x['assortment'])])*b.D(x['quantity']) for x in r.rows(ret))==cfg['refund_minor']
 assert [m.href(p['assortment']) for p in r.rows(order)]==[m.href(p['assortment']) for p in r.rows(demand)]
 assert m.href(demand['customerOrder'])==m.MS+'entity/customerorder/'+order['id']
 assert m.href(ret['demand'])==m.MS+'entity/demand/'+demand['id']
 assert [m.href(x) for x in order['demands']]==[m.MS+'entity/demand/'+demand['id']]
 assert [m.href(x) for x in demand['returns']]==[m.MS+'entity/salesreturn/'+ret['id']]
 assert not order.get('payments') and not ret.get('payments'),'Additional payment appeared; inspect before correction'
 assert len(pay['operations'])==1 and m.href(pay['operations'][0])==m.MS+'entity/demand/'+demand['id']
 assert [m.href(x) for x in demand['payments']]==[m.MS+'entity/paymentin/'+pay['id']]
 candidates={}
 goals=copy.deepcopy(before);bodies={}
 for typ,d in before.items():
  goal=goals[typ];target=cfg['refund_minor'] if typ=='salesreturn' else cfg['sale_minor']
  goal['sum']=target;goal['rate']={'currency':m.meta(base),'value':1}
  body={}
  if r.currency(d)!=m.href(base) or b.D(d['rate'].get('value',1))!=1:body['rate']=goal['rate']
  if typ!='paymentin':
   body['positions']=[]
   for idx,old in enumerate(r.rows(d)):
    q={k:copy.deepcopy(old[k]) for k in r.FIELDS if k in old};q['assortment']=m.meta(old['assortment']);q['price']=price_map[m.href(old['assortment'])]
    body['positions'].append(q);goal['positions']['rows'][idx]['price']=q['price']
  else:
   body['sum']=target;body['operations']=[{**m.meta(d['operations'][0]),'linkedSum':target}];goal['operations']=body['operations']
  bodies[typ]=body
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goals':goals,'bodies':bodies,'currencies':cc})
 expected=copy.deepcopy(before)
 for typ,body in bodies.items():
  fresh=z.read(t,cfg)
  for k,d in fresh.items():
   z.invariant(before[k],d);assert z.same(expected[k],d,k),'Concurrent edit'
  if not z.same(before[typ],goals[typ],typ):z.write(db,cfg,typ,body)
  expected[typ]=goals[typ];after=z.read(t,cfg)
  save(db,'readback:'+typ,{'at':m.now(),'documents':after})
  for k,d in after.items():
   z.invariant(before[k],d);assert z.same(expected[k],d,k),'Readback mismatch; stop without replay'
  save(db,'verified:'+typ,{'status':'verified','at':m.now()})
 final=z.read(t,cfg)
 for typ,d in final.items():
  z.invariant(before[typ],d);assert z.same(goals[typ],d,typ)
 for typ in ('customerorder','demand'):assert b.D(final[typ]['payedSum'])==cfg['sale_minor']
 assert b.D(final['paymentin']['operations'][0]['linkedSum'])==cfg['sale_minor']
 assert not final['salesreturn'].get('payments') and b.D(final['salesreturn'].get('payedSum'))==0
 assert z.ccstate(cc)==z.ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:v1',{'status':'verified_four_documents','at':m.now(),'documents':final,'sale_minor':cfg['sale_minor'],'refund_minor':cfg['refund_minor'],'refund_payment_candidates':list(candidates),'refund_payment_linked':False,'refund_payment_changed':False,'positions_quantity_order_links_preserved':True,'currency_settings_unchanged':True,'bulk_enabled':False})
 print('Authorized sale and partial return amounts verified; inspect private refund-payment search.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected partial-chain correction stopped; inspect private journal.');sys.exit(1)
