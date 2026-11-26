"""Read-only all-document currency and migration amount audit; private results only."""
import collections,concurrent.futures,copy,sys,traceback
import cny_migration_backup_20261125 as b
m=b.m;P='all_document_currency_audit_post_incoming:'
def save(db,k,v):b.put(db,P+k,v)
def chref(d):return m.href(d.get('rate',{}).get('currency',{})).split('?')[0]
def audit(task):
 typ,count=task;t=b.ReadOnly();db=m.Cache(t)
 cc=db.get(b.ROOT+P+'currencies:v1')['rows'];iso={m.href(c):c['isoCode'] for c in cc};base=next(m.href(c) for c in cc if c.get('default'))
 plans={}
 for start in range(0,count,2000):
  offsets=list(range(start,min(start+2000,count),100))
  keys=[b.ROOT+'verified_plan:'+typ+':page:'+str(o) for o in offsets]
  pp=t.request(db.base,'telegram_api_cache',params={'cache_key':'in.('+','.join(keys)+')','select':'payload','limit':1000})
  assert len(pp)==len(keys),'Incomplete private plan page set'
  for page in pp:
   for p in page['payload']['records']:plans[p['id']]=p
 assert len(plans)==count
 totals=collections.Counter();rates=collections.Counter();seen=set();offset=0;expected_count=None
 while True:
  page=t.request(m.MS,'entity/'+typ,params={'limit':1000,'offset':offset,'order':'id,asc'})
  if expected_count is None:expected_count=page['meta']['size']
  assert page['meta']['size']==expected_count,'Document count changed during read'
  records=[]
  for d in page['rows']:
   assert d['id'] not in seen;seen.add(d['id']);flags=[];p=plans.get(d['id']);cur=chref(d);ciso=iso.get(cur);rate=b.D(d.get('rate',{}).get('value',1));amount=b.D(d.get('sum'))
   if not d.get('rate'):flags.append('no_explicit_currency')
   elif ciso!='CNY':flags.append('not_cny')
   elif cur!=base:flags.append('nonbase_cny_reference')
   if d.get('rate') and rate!=1:flags.append('nonunit_internal_rate')
   if p:
    goal=b.D(p['actual_minor']);target=b.D(p['target_minor']);original=b.D(p['original_line_model_minor'])
    if amount==goal:flags.append('matches_original_conversion_total')
    else:
     flags.append('differs_from_original_conversion_total')
     if amount>0 and target>0 and abs(b.R(amount/12)-target)<=1 and abs(amount-goal)>1:flags.append('suspected_unconverted_amount')
     if original>0 and amount==original and original!=goal:flags.append('amount_equals_original_ruble_total')
   else:flags.append('not_in_original_backup')
   totals.update(flags);rates[(ciso or 'implicit_or_unknown',str(rate),cur==base)]+=1
   records.append({'id':d['id'],'name':d.get('name'),'moment':d.get('moment'),'applicable':d.get('applicable'),'sum_minor':d.get('sum'),'currency_href':cur,'currency_iso':ciso,'rate':str(rate),'positions_count':d.get('positions',{}).get('meta',{}).get('size') if isinstance(d.get('positions'),dict) else None,'original_converted_minor':p.get('actual_minor') if p else None,'original_target_minor':p.get('target_minor') if p else None,'flags':flags})
  save(db,'records:'+typ+':'+str(offset),{'at':m.now(),'type':typ,'rows':records})
  save(db,'progress:'+typ,{'at':m.now(),'status':'running','checked':len(seen),'total':expected_count})
  if len(seen)==expected_count:break
  assert page['rows'];offset+=len(page['rows'])
 result={'type':typ,'status':'complete','at':m.now(),'documents':len(seen),'flags':dict(totals),'rates':[{'iso':k[0],'rate':k[1],'base':k[2],'documents':v} for k,v in rates.items()],'backup_documents_missing_live':len(set(plans)-seen),'ms_writes':0}
 save(db,'result:'+typ,result);return result
def main():
 t=b.ReadOnly();db=m.Cache(t)
 assert not db.get(b.ROOT+P+'result:v1'),'Existing audit: use a new audit key if repeating'
 cc=b.fullrows(t,'entity/currency');save(db,'currencies:v1',{'at':m.now(),'rows':cc})
 mf=db.get(b.ROOT+'backup_manifest:v1');tasks=[(x['type'],x['count']) for x in mf['counts']]
 extra=db.get(b.ROOT+'scope_extra:inventory')
 if extra:tasks.append(('inventory',extra['count']))
 save(db,'started:v1',{'at':m.now(),'types':len(tasks),'ms_writes':0})
 results=[];errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(audit,x):x for x in tasks}
  for f in concurrent.futures.as_completed(futures):
   try:results.append(f.result())
   except Exception as e:errors.append({'type':futures[f][0],'detail':str(e)})
   save(db,'overall_progress:v1',{'at':m.now(),'types_complete':len(results),'types_failed':len(errors),'types_total':len(tasks),'errors':errors,'ms_writes':0})
 save(db,'result:v1',{'status':'complete' if not errors else 'incomplete','at':m.now(),'types':results,'errors':errors,'ms_writes':0})
 print('Read-only all-document currency audit finished; results private.')
 assert not errors
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only audit stopped; inspect private diagnostics.');sys.exit(1)
