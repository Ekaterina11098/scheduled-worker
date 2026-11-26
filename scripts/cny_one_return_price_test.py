"""Attempt price conversion on exactly one existing return; keep its source link."""
import copy,sys
import cny_single_document_test as s
import cny_document_rollout as r
b=s.b;m=s.m
def save(db,key,obj):s.save(db,'return_price:'+key,obj)
def shape(d):
 return [[p['id'],r.number(p['quantity']),m.href(p['assortment']),r.number(p.get('discount')),r.number(p.get('vat')),p.get('vatEnabled')] for p in d['positions']['rows']]
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(s.ROOT+'return_price_config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_screenshot_return_price_conversion' and cfg['max_documents']==1
 assert not db.get(r.ROOT+'authorization:v1')['authorized'],'Bulk must remain paused'
 assert cfg['preserve_quantities'] and cfg['preserve_position_order'] and cfg['preserve_demand_link']
 path='entity/salesreturn/'+cfg['document_id'];basis_path='entity/demand/'+cfg['basis_id']
 before=s.getdoc(t,path);basis=s.getdoc(t,basis_path)
 currencies=b.fullrows(t,'entity/currency');default=next(c for c in currencies if c.get('default'))
 assert default['isoCode']=='CNY'
 assert before['rate']['currency']['id']==default['id'] and b.D(before['rate'].get('value',1))==1
 assert m.href(before['demand'])==m.MS+basis_path
 page=db.get(b.ROOT+'backup:salesreturn:page:'+str(cfg['baseline_offset']))
 original=next(d for d in page['documents'] if d['id']==cfg['document_id'])
 assert b.D(original['sum'])==b.D(cfg['original_rub_minor'])
 assert shape(before)==shape(original),'Original quantity, assortment, position order or tax fields changed'
 plan=b.plan(original,original['positions']['rows'])
 assert b.D(plan['actual_minor'])==b.D(cfg['target_cny_minor'])
 body={'positions':[]}
 for old,price in zip(before['positions']['rows'],plan['price_minor']):
  p={k:copy.deepcopy(old[k]) for k in ('id','quantity','discount','vat','vatEnabled','pack','slot','things','country','gtd') if k in old}
  p['assortment']=m.meta(old['assortment']);p['price']=int(price);body['positions'].append(p)
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'basis':basis,'original':original,'body':body,'target_minor':cfg['target_cny_minor']})
 fresh=s.getdoc(t,path);assert r.signature(fresh,'salesreturn')==r.signature(before,'salesreturn'),'Return changed before writing'
 if b.D(before['sum'])!=b.D(cfg['target_cny_minor']):
  s.NarrowWriter(db,path).write_once(path,'PUT',body,'return_price:price_only_intent:v1')
 after=s.getdoc(t,path);basis_after=s.getdoc(t,basis_path)
 save(db,'readback:v1',{'at':m.now(),'after':after,'basis_after':basis_after})
 assert shape(after)==shape(before),'Return quantity, assortment or position order changed'
 assert m.href(after['demand'])==m.href(before['demand'])
 assert after['id']==before['id'] and after['name']==before['name']
 assert r.signature(basis_after,'demand')==r.signature(basis,'demand'),'Demand changed'
 for key in ('description','moment','applicable','organization','agent','store'):
  assert before.get(key)==after.get(key),'Nonmonetary header changed: '+key
 success=(b.D(after['sum'])==b.D(cfg['target_cny_minor']) and after['rate']['currency']['id']==default['id'] and b.D(after['rate'].get('value',1))==1)
 if success:
  assert [b.D(p['price']) for p in after['positions']['rows']]==[b.D(p) for p in plan['price_minor']]
 else:
  assert r.signature(after,'salesreturn')==r.signature(before,'salesreturn'),'Unexpected partial change'
 response=db.get(s.ROOT+'return_price:price_only_intent:v1:response') or {}
 save(db,'result:v1',{'status':'verified' if success else 'rejected_unchanged','at':m.now(),'document_id':after['id'],'name':after['name'],'before_minor':before['sum'],'after_minor':after['sum'],'target_minor':cfg['target_cny_minor'],'currency':after['rate']['currency']['isoCode'],'rate':after['rate'].get('value',1),'positions':len(after['positions']['rows']),'quantity':r.number(sum(p['quantity'] for p in after['positions']['rows'])),'positions_unchanged':True,'basis_unchanged':True,'basis_link_preserved':True,'http_status':response.get('http_status'),'diagnostics':response.get('detail')})
 print('Single existing return price test read back; private result saved. Bulk remains paused.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error),'error':type(error).__name__})
  except Exception:pass
  print('Single-return price test stopped; inspect private diagnostics before retry.');sys.exit(1)
