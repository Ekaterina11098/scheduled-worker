"""Verify private journal read/write and unsettled MS state without any MS mutation."""
import copy,sys,traceback,uuid
import cny_all_remaining_refs_apply as a
p=a.p;h=a.h;r=a.r;b=a.b;m=a.m;Q='journal_recovery_probe_20261127:'
def save(db,k,v):p.save(db,Q+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);auth=db.get(b.ROOT+p.P+'authorization:v1')
 assert auth and auth['authorized'] and auth['scope']=='remaining_ms_currency_references_only'
 proof={'at':m.now(),'nonce':uuid.uuid4().hex,'ms_writes':0}
 save(db,'write_read:v1',proof);assert db.get(b.ROOT+p.P+Q+'write_read:v1')==proof
 initial=db.get(b.ROOT+p.P+'reconciled_start:v1') or db.get(b.ROOT+p.P+'start:v1')
 currencies=b.fullrows(t,'entity/currency');assert h.h.ccstate(currencies)==h.h.ccstate(initial['currencies'])
 wh=h.warehouse(t);stats=[];errors=[]
 for offset in (18820,19220):
  key='apply:customerorder:'+str(offset);snap=db.get(b.ROOT+p.P+key+':snapshot')
  assert snap and db.get(b.ROOT+p.P+key+':intent')
  current=r.live(t,'customerorder',list(snap['before']));pending=[];ready=[]
  for i,d in current.items():
   a.invariant(snap['before'][i],d,'customerorder')
   sig=a.signature(d,'customerorder');goal=a.signature(snap['goals'][i],'customerorder')
   assert sig in (goal,a.signature(snap['before'][i],'customerorder')),'Unexpected document edit'
   (ready if sig==goal else pending).append(i)
  save(db,'batch:'+str(offset),{'at':m.now(),'before':snap['before'],'goals':snap['goals'],'current':current,'pending':pending,'ready':ready})
  stats.append({'offset':offset,'documents':len(current),'pending':len(pending),'ready':len(ready)})
 changed=[]
 old=initial['warehouse_quantities']
 for product in sorted(set(old)|set(wh)):
  for store in sorted(set(old.get(product,{}))|set(wh.get(product,{}))):
   if old.get(product,{}).get(store)!=wh.get(product,{}).get(store):changed.append({'product':product,'store':store,'before':old.get(product,{}).get(store),'after':wh.get(product,{}).get(store)})
 save(db,'result:v1',{'status':'verified','at':m.now(),'journal_read_write_verified':True,'ms_read_verified':True,'batches':stats,'warehouse_quantities':wh,'warehouse_differences':changed,'warehouse_quantities_unchanged':not changed,'currency_settings_unchanged':True,'ms_writes':0})
 print('Private journal read/write and unsettled document state verified without MS writes.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Recovery probe stopped; no MS writes.');sys.exit(1)
