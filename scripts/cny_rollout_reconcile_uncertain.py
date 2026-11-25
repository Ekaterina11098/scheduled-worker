"""Read-only reconciliation of uncertain document conversion batches."""
import sys
import cny_document_rollout as r
b=r.b;m=r.m
def main():
 t=b.ReadOnly();db=m.Cache(t);summary=[]
 for typ,offset in [('supply',100),('enter',200),('loss',100),('purchasereturn',0)]:
  key='batch:'+typ+':'+str(offset);batch=db.get(r.ROOT+key);assert batch
  expected={p['id']:p['expected'] for p in batch['plans']}
  old={d['id']:d for d in batch['live_before']}
  fresh=r.live(t,typ,list(expected))
  counts={'expected':0,'unchanged':0,'other':0};details=[]
  for identifier,d in fresh.items():
   sig=r.signature(d,typ)
   state='expected' if sig==expected[identifier] else ('unchanged' if sig==r.signature(old[identifier],typ) else 'other')
   counts[state]+=1
   if state!='expected':details.append({'id':identifier,'name':d.get('name'),'state':state,'live':d,'expected':expected[identifier],'before':old[identifier]})
  result={'status':'read_only_reconciled','at':m.now(),'type':typ,'offset':offset,'counts':counts,'details':details,'ms_writes':0}
  r.save(db,'reconcile:'+typ+':'+str(offset),result)
  summary.append({'type':typ,'offset':offset,'counts':counts})
 r.save(db,'reconciliation:v1',{'status':'complete','at':m.now(),'sections':summary,'ms_writes':0})
 print('Read-only reconciliation saved privately. No mutation was repeated.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:r.save(m.Cache(b.ReadOnly()),'reconciliation:error:v1',{'status':'failed','detail':str(error),'at':m.now()})
  except Exception:pass
  print('Read-only reconciliation stopped; inspect private diagnostics.');sys.exit(1)
