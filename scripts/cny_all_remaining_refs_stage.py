"""Bounded rollout sections after successful category-level preservation checks."""
import argparse,sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;b=a.b;m=a.m
def main(stage,index):
 db=m.Cache(b.ReadOnly());assert db.get(b.ROOT+p.P+'canary:v1')['status']=='verified'
 if stage=='other':types=('purchaseorder','invoicein','move','loss','purchasereturn','salesreturn','supply','enter','invoiceout')
 elif stage=='finance':types=('cashin','cashout','paymentin','paymentout')
 else:types=(stage,)
 summary=[]
 for typ in types:
  info=db.get(b.ROOT+p.P+'type:'+typ);n=len(info['candidates'])
  start=20+5000*index if stage in ('customerorder','demand') else 20
  end=start+5000 if stage in ('customerorder','demand') else max(40,((n+19)//20)*20)
  if start<n:a.run(typ,start,end,100)
  summary.append({'type':typ,'start':start,'end':min(end,n),'candidates':n})
 p.save(db,'stage:'+stage+':'+str(index),{'status':'verified','at':m.now(),'sections':summary})
 print('Authorized reference-only stage verified; private checkpoints saved.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('stage');ap.add_argument('--index',type=int,default=0);args=ap.parse_args()
 try:main(args.stage,args.index)
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:stage:'+args.stage+':'+str(args.index),{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Rollout stopped at a guarded checkpoint.');sys.exit(1)
