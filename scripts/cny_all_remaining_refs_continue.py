"""Small disjoint continuation sections; existing write intents are never replayed."""
import argparse,sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;b=a.b;m=a.m
OTHER=('purchaseorder','invoicein','move','loss','purchasereturn','salesreturn','supply','enter','invoiceout')
def covered(db,typ):
 info=db.get(b.ROOT+p.P+'type:'+typ);ids=info['candidates'];seen=set()
 for off in ([0] if ids else [])+list(range(20,len(ids),100)):
  key='apply:'+typ+':'+str(off);proof=db.get(b.ROOT+p.P+key+':verified')
  expected=ids[off:off+(20 if off==0 else 100)]
  assert proof and proof['count']==len(expected),'Missing verified continuation checkpoint'
  assert not seen.intersection(expected);seen.update(expected)
 assert seen==set(ids),'Incomplete candidate coverage'
 return len(ids)
def main(stage,index):
 t=b.ReadOnly();db=m.Cache(t)
 if db.get(b.ROOT+p.P+'result:v1'):
  assert db.get(b.ROOT+p.P+'result:v1')['status']=='verified';print('Existing complete reconciliation preserved.');return
 assert db.get(b.ROOT+p.P+'canary_extended:v1')['status']=='verified'
 if stage=='other':
  prior=db.get(b.ROOT+p.P+'stage:other:0')
  if prior and prior['status']=='verified':print('Completed document categories preserved; final audit will recheck.');return
  for typ in OTHER:
   n=len(db.get(b.ROOT+p.P+'type:'+typ)['candidates'])
   if n>20:a.run(typ,20,max(40,((n+19)//20)*20),100)
  p.save(db,'stage:other:0',{'status':'verified','at':m.now(),'continued':True,'counts':{typ:covered(db,typ) for typ in OTHER}})
 elif stage in ('customerorder','demand'):
  start=20+1000*index
  prior=db.get(b.ROOT+p.P+'section:'+stage+':'+str(start))
  if prior and prior['status']=='verified':
   p.save(db,'continuation:'+stage+':'+str(index),{'status':'verified','at':m.now(),'reused_verified_section':True});print('Completed section preserved; final audit will recheck.');return
  n=len(db.get(b.ROOT+p.P+'type:'+stage)['candidates'])
  if start<n:a.run(stage,start,start+1000,100)
  p.save(db,'continuation:'+stage+':'+str(index),{'status':'verified','at':m.now(),'start':start,'end':min(start+1000,n)})
 elif stage in ('mark_customerorder','mark_demand'):
  typ=stage.removeprefix('mark_');n=covered(db,typ)
  for i in range(8):
   lo=20+5000*i
   p.save(db,'stage:'+typ+':'+str(i),{'status':'verified','at':m.now(),'continued':True,'start':lo,'end':min(lo+5000,n),'coverage_verified':True})
 elif stage=='finance':
  for typ in ('paymentin','paymentout','cashin','cashout'):
   n=len(db.get(b.ROOT+p.P+'type:'+typ)['candidates']);start=20+1000*index
   if start<n:a.run(typ,start,start+1000,100)
  p.save(db,'continuation:finance:'+str(index),{'status':'verified','at':m.now()})
 elif stage=='mark_finance':
  p.save(db,'stage:finance:0',{'status':'verified','at':m.now(),'continued':True,'counts':{typ:covered(db,typ) for typ in ('paymentin','paymentout','cashin','cashout')}})
 else:raise ValueError('Unknown continuation stage')
 print('Continuation section verified; confirmed changes not repeated.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('stage');ap.add_argument('--index',type=int,default=0);args=ap.parse_args()
 try:main(args.stage,args.index)
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:continuation:'+args.stage+':'+str(args.index),{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Continuation stopped at a protected checkpoint.');sys.exit(1)
