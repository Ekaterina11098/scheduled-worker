"""Focused read-only document/audit proof, preserving previous movement reports."""
import os,json,time,requests
from stock_deploy_support import runtime_db
from stock_operation_store import Store,canonical
from stock_execution_fence import cloud_writer
ROOT='technical:owner-full-movement:2026-11-27:regina1'
BASE='https://api.moysklad.ru/api/remap/1.2'
with cloud_writer(runtime_db()):
 with runtime_db() as db:
  s=Store(db,postgres=True);d=json.loads(s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone()[0]);db.commit()
  x={'started':time.time(),'documents':{},'audits':{},'coverage':[],'errors':[],'business_writes':0};d['focused']=x
  session=requests.Session();session.headers.update({'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept':'application/json;charset=utf-8','X-Lognex-Accept-Timezone':'Europe/Moscow'})
  def save():
   with s.transaction():s.sql('UPDATE stock_runs SET snapshot=? WHERE id=?',(canonical(d),ROOT))
  def get(url,**params):
   assert url.startswith(BASE+'/')
   for attempt in range(3):
    r=session.get(url,params=params,timeout=(10,45))
    if r.status_code in (429,500,502,503,504) and attempt<2:time.sleep(min(10,max(1,float(r.headers.get('Retry-After',1)))));continue
    r.raise_for_status();time.sleep(.2);return r.json()
  def rows(url,**params):
   out=[];seen=set()
   while url:
    assert url not in seen;seen.add(url);v=get(url,**params);params={};out+=v['rows'];url=v.get('meta',{}).get('nextHref')
   return out
  href=d['products'][0]['meta']['href'];refs={}
  for k,values in d['reports'].items():
   if k.startswith('turnover_operations:'):
    for row in values:refs[row['operation']['meta']['href']]=row['operation']
  # Explicit first-stock source and its source-side return documents.
  for row in d['reports'].get('stock_operations:'+d['products'][0]['id'],[]):
   if row.get('moment','')>='2026-11-19':refs[row['operation']['meta']['href']]=row['operation']
  kinds=['demand','supply','move','enter','loss','salesreturn','purchasereturn','inventory','retaildemand','retailsalesreturn','processing','productionstagecompletion','customerorder']
  for kind in kinds:
   x['phase']='list:'+kind;save()
   try:
    docs=rows(BASE+'/entity/'+kind,filter='assortment='+href+';moment>=2026-11-19 00:00:00',limit=100)
    x['coverage'].append({'type':kind,'method':'exact_assortment','count':len(docs)})
    for doc in docs:refs[doc['meta']['href']]=doc
   except Exception as exc:x['errors'].append({'phase':kind,'error':str(exc)})
  queue=list(refs);seen=set()
  while queue:
   url=queue.pop(0)
   if url in seen:continue
   seen.add(url);x['phase']='document:'+url.rsplit('/',1)[-1];save()
   try:
    doc=get(url);parts=rows(url+'/positions',limit=1000)
    match=[p for p in parts if p.get('assortment',{}).get('meta',{}).get('href')==href]
    clean={k:v for k,v in doc.items() if k!='positions'};clean['matched_positions']=match
    key=doc['meta']['type']+':'+doc['id'];x['documents'][key]=clean
    events=rows(url+'/audit',limit=1000)
    # Keep full audit privately; project only this product in analysis.
    x['audits'][key]=events
    for field in ('customerOrder','demand','salesReturn','inventory'):
     linked=doc.get(field,{}).get('meta',{}).get('href')
     if linked and linked not in seen:queue.append(linked)
    save()
   except Exception as exc:x['errors'].append({'phase':url,'error':str(exc)});save()
  x.update(complete=True,finished=time.time());d.update(status='focused_complete',completed=time.time());save()
  print(json.dumps({'complete':True,'documents':len(x['documents']),'errors':len(x['errors']),'business_writes':0}))
