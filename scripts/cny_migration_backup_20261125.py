"""Read-only complete currency-migration source backup. No live MS mutations."""
import argparse,concurrent.futures,collections,hashlib,json,sys,time
from decimal import Decimal,ROUND_HALF_UP,ROUND_FLOOR
import fbs_document_chain as m
ROOT='ms_currency_cny_migration:20261125:'
class ReadOnly(m.Transport):
 def request(self,base,path,method='GET',body=None,params=None):
  if base==m.MS and method!='GET':raise m.Stop('Backup permits MS GET only')
  if base==m.WB:raise m.Stop('WB out of scope')
  return super().request(base,path,method,body,params)
def D(x):return Decimal(str(x or 0))
def R(x):return x.quantize(Decimal(1),rounding=ROUND_HALF_UP)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def put(db,key,payload):
 for i in range(4):
  try:db.put(ROOT+key,payload);return
  except Exception:
   try:
    if db.get(ROOT+key)==payload:return
   except Exception:pass
   if i==3:raise
   time.sleep(i+1)
def fullrows(t,path,params=None):
 rows=[]
 while True:
  page=t.request(m.MS,path,params={**(params or {}),'limit':1000,'offset':len(rows)})
  rows+=page['rows']
  if len(rows)==page['meta']['size']:return rows
  assert page['rows'] and len(rows)<page['meta']['size']
def initialize():
 t=ReadOnly();db=m.Cache(t)
 if db.get(ROOT+'backup_manifest:v1'):return
 auth=db.get(ROOT+'authorization:v1')
 assert auth['authorized'] and auth['unit_price_decimals']==2 and not auth['additional_position_rows_allowed']
 pf=db.get(ROOT+'preflight:v1')
 assert pf['status']=='complete'
 counts=[]
 for x in pf['counts']:
  n=t.request(m.MS,'entity/'+x['type'],params={'limit':1})['meta']['size']
  counts.append({'type':x['type'],'count':n})
 auxiliary={}
 for typ in ('currency','organization','store','product','bundle','variant','service'):
  rows=fullrows(t,'entity/'+typ,{'filter':'archived=false'}) if typ in ('store','product','bundle','variant','service') else fullrows(t,'entity/'+typ)
  if typ in ('store','product','bundle','variant','service'):
   rows+=fullrows(t,'entity/'+typ,{'filter':'archived=true'})
  assert len({r['id'] for r in rows})==len(rows)
  for i in range(0,len(rows),100):
   part=rows[i:i+100];put(db,'backup_aux:'+typ+':'+str(i),{'type':typ,'rows':part,'sha256':digest(part),'at':m.now()})
  auxiliary[typ]={'count':len(rows)}
  if typ=='organization':
   for org in rows:
    accounts=fullrows(t,'entity/organization/'+org['id']+'/accounts')
    put(db,'backup_accounts:'+org['id'],{'rows':accounts,'sha256':digest(accounts)})
 currencies=fullrows(t,'entity/currency')
 assert all(x['isoCode']=='RUB' for x in currencies)
 manifest={'status':'initialized','created_at':m.now(),'counts':counts,'auxiliary':auxiliary,'currencies':currencies,'ms_writes':0}
 put(db,'backup_manifest:v1',manifest)
 print('Private baseline manifest and catalogue backups verified.')
def plan(doc,positions):
 prices=[R(D(p.get('price'))/12) for p in positions]
 goal=R(D(doc.get('sum'))/12)
 def factor(p):
  f=D(p.get('quantity'))*(100-D(p.get('discount')))/100
  if doc.get('vatEnabled') and not doc.get('vatIncluded') and p.get('vatEnabled',True):f*=1+D(p.get('vat'))/100
  return f
 factors=[factor(p) for p in positions]
 old=sum((R(D(p.get('price'))*f) for p,f in zip(positions,factors)),Decimal(0))
 base=sum((R(price*f) for price,f in zip(prices,factors)),Decimal(0))
 if positions and old!=D(doc.get('sum')):raise m.Stop('Original line calculation does not reconcile')
 best=(abs(base-goal),Decimal(0),-1,Decimal(0),base)
 for i,(p,f) in enumerate(zip(prices,factors)):
  if f<=0:continue
  desired=(goal-base+R(p*f))/f
  floor=int(desired.to_integral_value(rounding=ROUND_FLOOR))
  for candidate in range(max(0,floor-3),max(0,floor+4)+1):
   achieved=base-R(p*f)+R(D(candidate)*f)
   score=(abs(achieved-goal),abs(D(candidate)-p),i,D(candidate),achieved)
   if score[:3]<best[:3]:best=score
 if best[2]>=0:prices[best[2]]=best[3]
 return {'target_minor':str(goal),'actual_minor':str(best[4] if positions else goal),'deviation_minor':str((best[4] if positions else goal)-goal),'price_minor':[str(x) for x in prices],'adjusted_index':best[2],'rounded_line_base_minor':str(base),'original_line_model_minor':str(old)}
def backup_page(task):
 typ,offset,count=task
 t=ReadOnly();db=m.Cache(t);key='backup:'+typ+':page:'+str(offset)
 existing=db.get(ROOT+key)
 if existing and existing.get('status')=='complete':
  assert existing['sha256']==digest(existing['documents'])
  return {'type':typ,'offset':offset,'documents':len(existing['documents']),'positions':existing['positions'],'reused':True}
 batch=t.request(m.MS,'entity/'+typ,params={'limit':100,'offset':offset,'order':'id,asc','expand':'positions'})
 assert batch['meta']['size']==count and len(batch['rows'])==min(100,count-offset)
 docs=[];plans=[];position_count=0
 for doc in batch['rows']:
  pp=doc.get('positions')
  positions=[]
  if isinstance(pp,dict):
   expected=pp.get('meta',{}).get('size')
   assert isinstance(expected,int)
   positions=pp.get('rows',[])
   while len(positions)<expected:
    extra=t.request(m.MS,'entity/'+typ+'/'+doc['id']+'/positions',params={'limit':1000,'offset':len(positions)})
    assert extra.get('rows');positions+=extra['rows']
   assert len(positions)==expected
   doc['positions']={**pp,'rows':positions}
  position_count+=len(positions)
  docs.append(doc)
  p=plan(doc,positions)
  money_fields={k:v for k,v in doc.items() if k not in ('sum','rate','positions') and (isinstance(v,(int,float)) and v!=0 or isinstance(v,dict) and k in ('overhead','commissionPeriod'))}
  plans.append({'id':doc['id'],'name':doc.get('name'),'type':typ,'source_updated':doc.get('updated'),**p,'other_nonzero_numeric_fields':money_fields})
 result={'status':'complete','type':typ,'offset':offset,'read_at':m.now(),'documents':docs,'positions':position_count,'sha256':digest(docs),'ms_writes':0}
 put(db,key,result)
 put(db,'dry_plan:'+typ+':page:'+str(offset),{'status':'complete','records':plans,'source_sha256':result['sha256']})
 return {'type':typ,'offset':offset,'documents':len(docs),'positions':position_count,'reused':False}
def backup(group):
 t=ReadOnly();db=m.Cache(t);manifest=db.get(ROOT+'backup_manifest:v1')
 assert manifest
 selected=[x for x in manifest['counts'] if (group=='orders' and x['type']=='customerorder') or (group=='shipments' and x['type']=='demand') or (group=='other' and x['type'] not in ('customerorder','demand'))]
 tasks=[(x['type'],o,x['count']) for x in selected for o in range(0,x['count'],100)]
 put(db,'backup_status:'+group,{'status':'running','started_at':m.now(),'pages_total':len(tasks),'ms_writes':0})
 completed=[];failed=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futures={pool.submit(backup_page,task):task for task in tasks}
  for f in concurrent.futures.as_completed(futures):
   task=futures[f]
   try:completed.append(f.result())
   except Exception as e:failed.append({'type':task[0],'offset':task[1],'reason':str(e)})
   if (len(completed)+len(failed))%10==0:
    put(db,'backup_status:'+group,{'status':'running','updated_at':m.now(),'pages_complete':len(completed),'pages_failed':len(failed),'pages_total':len(tasks),'ms_writes':0})
 result={'status':'complete' if not failed else 'incomplete','completed':completed,'failed':failed,'finished_at':m.now(),'ms_writes':0}
 put(db,'backup_result:'+group,result)
 print('Read-only private backup partition finished; live MS unchanged.')
 assert not failed
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['initialize','orders','shipments','other']);a=p.parse_args()
 initialize() if a.stage=='initialize' else backup(a.stage)
