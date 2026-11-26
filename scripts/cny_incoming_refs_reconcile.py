"""Read-only reconciliation of halted incoming correction."""
import sys,traceback
import cny_incoming_refs_apply as x
r=x.r;b=x.b;m=x.m;P=x.P
def main():
 t=b.ReadOnly();db=m.Cache(t);ss=db.get(b.ROOT+P+'batch:supply:0:snapshot');assert ss
 linked={}
 for typ,ds in ss['linked_before'].items():linked[typ]=r.live(t,typ,list(ds))
 after=r.live(t,'supply',list(ss['before']))
 checks=[]
 for i,d in after.items():
  x.h.inv(ss['before'][i],d);assert r.signature(d,'supply')==r.signature(ss['goals'][i],'supply')
 for typ,ds in linked.items():
  for i,d in ds.items():
   old=ss['linked_before'][typ][i]
   changes={k:{'before':old.get(k),'after':d.get(k)} for k in ('returns','payments','demands','losses') if old.get(k)!=d.get(k)}
   checks.append({'type':typ,'id':i,'signature_unchanged':r.signature(old,typ)==r.signature(d,typ),'list_changes':changes})
 wh=x.warehouse(t);orig=db.get(b.ROOT+P+'apply_started:v1')['warehouse_quantities']
 x.save(db,'reconcile:v1',{'at':m.now(),'status':'read','linked':linked,'linked_checks':checks,'supply_docs':after,'all_warehouse_quantities_preserved':wh==orig,'warehouse_quantities':wh})
 print('Read-only reconciliation saved privately.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  x.save(m.Cache(b.ReadOnly()),'error:reconcile:v1',{'detail':str(e),'trace':traceback.format_exc()});sys.exit(1)
