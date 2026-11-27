"""Run small reference-only checks across each affected document category."""
import sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;b=a.b;m=a.m
TYPES=('customerorder','demand','purchaseorder','invoicein','move','loss','purchasereturn','cashout','paymentin','paymentout','salesreturn','supply','enter','invoiceout','cashin')
def main():
 t=b.ReadOnly();db=m.Cache(t);pf=db.get(b.ROOT+p.P+'preflight:v1')
 assert pf and pf['status']=='complete'
 done=[]
 for typ in TYPES:
  info=db.get(b.ROOT+p.P+'type:'+typ)
  if not info['candidates']:continue
  a.run(typ,0,20);done.append(typ)
  p.save(db,'canary_progress:v1',{'at':m.now(),'verified_types':done})
 p.save(db,'canary:v1',{'status':'verified','at':m.now(),'types':done})
 print('Reference-only checks verified across affected document categories.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:canary:v1',{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Category check stopped; inspect private diagnostic.');sys.exit(1)
