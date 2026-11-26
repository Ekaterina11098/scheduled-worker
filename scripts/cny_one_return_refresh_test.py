"""Test a single explicitly authorized existing return by an empty PUT only."""
import sys
import cny_single_document_test as s
import cny_document_rollout as r
b=s.b;m=s.m
def save(db,key,value):s.save(db,'return_refresh:'+key,value)
def shape(d):return [(p['id'],str(b.D(p['quantity']).normalize()),m.href(p['assortment'])) for p in d['positions']['rows']]
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(s.ROOT+'return_refresh_config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_existing_salesreturn_refresh_only' and cfg['max_documents']==1
 assert cfg['write_body']=='empty_object' and not cfg['quantity_changes_allowed'] and not cfg['position_order_changes_allowed']
 bulk=db.get(r.ROOT+'authorization:v1');assert not bulk['authorized']
 path='entity/salesreturn/'+cfg['document_id'];basis_path='entity/demand/'+cfg['demand_id']
 before=s.getdoc(t,path);basis=s.getdoc(t,basis_path)
 save(db,'initial_read:v1',{'at':m.now(),'before':before,'basis':basis})
 assert m.href(before['demand'])==m.MS+basis_path,'Unexpected source demand'
 assert basis['rate']['currency']['isoCode']=='CNY' and b.D(basis['rate'].get('value',1))==12,'Source demand is not CNY at rate 12'
 if before['rate']['currency']['isoCode']=='CNY':
  baseline=db.get(b.ROOT+'backup:salesreturn:page:'+str(cfg.get('baseline_offset',0)))
  old=next(x for x in baseline['documents'] if x['id']==before['id'])
  target=b.plan(old,old['positions']['rows'])
  save(db,'result:v1',{'status':'read_only_verified' if b.D(before['sum'])==b.D(target['actual_minor']) and shape(before)==shape(old) else 'read_only_mismatch','outcome':'already_cny_without_resave','at':m.now(),'document_id':before['id'],'name':before['name'],'before_currency':old['rate']['currency']['meta']['href'],'after_currency':'CNY','original_sum':old['sum'],'after_sum':before['sum'],'target_sum':target['actual_minor'],'rows':len(shape(before)),'quantity':str(sum((b.D(p['quantity']) for p in before['positions']['rows']),b.D(0))),'positions_unchanged':shape(before)==shape(old),'ms_documents_written':0})
  print('Selected return already uses CNY; observed read-only and no resave attempted.')
  return
 assert before['rate']['currency']['isoCode']=='RUB','Unexpected initial return currency'
 # Preserve the actual source, not a reconstructed or newly created return.
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'basis':basis,'shape':shape(before),'body':{},'ms_documents_in_scope':1})
 fresh=s.getdoc(t,path);assert r.signature(fresh,'salesreturn')==r.signature(before,'salesreturn')
 s.NarrowWriter(db,path).write_once(path,'PUT',{},'return_refresh:empty_put_intent:v1')
 after=s.getdoc(t,path);basis_after=s.getdoc(t,basis_path)
 save(db,'readback:v1',{'at':m.now(),'after':after,'basis_after':basis_after})
 assert shape(after)==shape(before),'Return quantity, assortment or order changed'
 assert after['id']==before['id'] and after['name']==before['name']
 assert m.href(after['demand'])==m.href(before['demand'])
 assert r.signature(basis_after,'demand')==r.signature(basis,'demand'),'Source demand changed'
 code=after['rate']['currency']['isoCode']
 if code=='CNY':
  outcome='currency_changed'
  monetary_ok=b.D(after['sum'])==b.R(b.D(before['sum'])/12)
  assert b.D(after['rate'].get('value',1))==12
 elif code=='RUB':
  outcome='no_currency_change'
  monetary_ok=r.signature(after,'salesreturn')==r.signature(before,'salesreturn')
 else:raise m.Stop('Unexpected currency after refresh')
 save(db,'result:v1',{'status':'verified' if monetary_ok else 'monetary_mismatch','at':m.now(),'outcome':outcome,'document_id':before['id'],'name':before['name'],'before_currency':before['rate']['currency']['isoCode'],'after_currency':code,'before_sum':before['sum'],'after_sum':after['sum'],'rate':after['rate'].get('value',1),'rows':len(shape(before)),'quantity':str(sum((b.D(p['quantity']) for p in before['positions']['rows']),b.D(0))),'positions_unchanged':True,'basis_unchanged':True,'body':{},'ms_documents_written':1,'monetary_check':monetary_ok})
 print('Single existing-return refresh test read back; private result saved. No bulk run.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error),'error':type(error).__name__})
  except Exception:pass
  print('Single-return test stopped; inspect private diagnostics.');sys.exit(1)
