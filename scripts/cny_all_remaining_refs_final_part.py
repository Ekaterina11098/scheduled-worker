"""Final all-document header, changed-position and warehouse reconciliation."""
import copy,sys,traceback
import cny_all_remaining_refs_apply as a
p=a.p;h=a.h;r=a.r;b=a.b;m=a.m
def main(group):
 assert group in ('orders','shipments','other')
 t=b.ReadOnly();db=m.Cache(t);start=db.get(b.ROOT+p.P+'reconciled_start:v1') or db.get(b.ROOT+p.P+'start:v1');pf=db.get(b.ROOT+p.P+'preflight:v1')
 if db.get(b.ROOT+p.P+'result:v1'):
  assert db.get(b.ROOT+p.P+'result:v1')['status']=='verified';print('Existing complete reconciliation preserved.');return
 assert pf['status']=='complete' and db.get(b.ROOT+p.P+'canary:v1')['status']=='verified'
 for stage in ('other','finance'):
  assert db.get(b.ROOT+p.P+'stage:'+stage+':0')['status']=='verified'
 for typ in ('customerorder','demand'):
  for idx in range(8):assert db.get(b.ROOT+p.P+'stage:'+typ+':'+str(idx))['status']=='verified'
 cc=b.fullrows(t,'entity/currency');assert h.h.ccstate(cc)==h.h.ccstate(start['currencies'])
 base=next(c for c in cc if c.get('default'));summary=[]
 selected=[typ for typ in start['types'] if (group=='orders' and typ=='customerorder') or (group=='shipments' and typ=='demand') or (group=='other' and typ not in ('customerorder','demand'))]
 for typ in selected:
  info=db.get(b.ROOT+p.P+'type:'+typ);before={}
  for off in range(0,info['count'],1000):
   for d in db.get(b.ROOT+p.P+'headers:'+typ+':'+str(off))['documents']:before[d['id']]=d
  after=b.fullrows(t,'entity/'+typ,{'order':'id,asc'});new={d['id']:d for d in after}
  assert set(before)<=set(new),'Original documents missing after correction'
  for i,old in before.items():
   d=new[i]
   for k in ('name','moment','applicable','sum','description','externalCode','vatEnabled','vatIncluded'):
    assert old.get(k)==d.get(k),'Original document header or total changed'
   for k in ('agent','organization','store','sourceStore','targetStore','customerOrder','purchaseOrder','demand','supply','contract','project','state'):
    assert m.href(old.get(k,{}))==m.href(d.get(k,{})),'Document relationship changed'
   for k in ('returns','payments','demands','losses','supplies','moves'):
    assert a.refs(old,k)==a.refs(d,k),'Related document set changed'
   if d.get('rate'):assert r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1,'Currency reference or rate remains uncorrected'
  for d in after:
   if d.get('rate'):assert r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1,'New document requires separate review'
  ids=info['candidates'];checked=0
  # Canary offset zero has at most twenty records; remaining sections use chunks of one hundred.
  offsets=([0] if ids else [])+list(range(20,len(ids),100))
  for off in offsets:
   key='apply:'+typ+':'+str(off);snap=a.read_snapshot(db,key+':snapshot')
   assert snap and db.get(b.ROOT+p.P+key+':verified'),'Missing verified checkpoint'
   current=r.live(t,typ,list(snap['before']))
   for i,d in current.items():
    a.invariant(snap['before'][i],d,typ)
    assert a.signature(d,typ)==a.signature(snap['goals'][i],typ),'Final saved position or allocation mismatch'
   p.save(db,'final:'+typ+':'+str(off),{'at':m.now(),'documents':current})
   checked+=len(current)
   p.save(db,'final_progress:v1',{'at':m.now(),'type':typ,'checked_in_type':checked,'total_in_type':len(ids),'types_complete':len(summary)})
  assert checked==len(ids),'Candidate coverage mismatch'
  summary.append({'type':typ,'documents_before':len(before),'documents_after':len(after),'normalized':checked,'new_documents':len(set(new)-set(before)),'nominal_sum_before_minor':info['nominal_sum_minor'],'nominal_sum_after_originals_minor':str(sum((b.D(new[i].get('sum')) for i in before),b.D(0)))})
  p.save(db,'final_type:'+typ,summary[-1])
 wh=h.warehouse(t);assert wh==start['warehouse_quantities'],'Warehouse quantities differ at final reconciliation'
 assert h.h.ccstate(b.fullrows(t,'entity/currency'))==h.h.ccstate(cc)
 result={'status':'verified','at':m.now(),'types':summary,'normalized':sum(x['normalized'] for x in summary),'all_document_prices_nominal_sums_quantities_rows_stores_links_preserved':True,'all_store_quantities_preserved':True,'all_documents_preserved':True,'all_currency_references_base_cny_rate_one':True,'business_conversion_rub_per_cny':12,'outside_ms_changes':False}
 result['group']=group
 p.save(db,'final_part:'+group,result)
 print('Complete currency reference reconciliation verified; no stock quantities changed.')
if __name__=='__main__':
 try:main(sys.argv[1])
 except Exception as e:
  try:p.save(m.Cache(b.ReadOnly()),'error:final_part:'+sys.argv[1],{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Final reconciliation stopped; inspect private diagnostic.');sys.exit(1)
