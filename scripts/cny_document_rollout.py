"""Checkpointed conversion of authorized MS documents; no accounting-currency switch."""
import argparse,copy,gzip,json,os,sys,urllib.request,urllib.error
from decimal import Decimal
import cny_migration_backup_20261125 as b
m=b.m;ROOT=b.ROOT+'document_rollout:'
FIN={'paymentin','paymentout','cashout'}
FIELDS=('id','quantity','discount','vat','vatEnabled','pack','slot','things','country','gtd','trackingCodes','trackingCodes_1162','customsDeclarationNumber')
def save(db,key,obj):b.put(db,'document_rollout:'+key,obj)
def rows(d):return d.get('positions',{}).get('rows',[]) if isinstance(d.get('positions'),dict) else []
def currency(d):return m.href(d.get('rate',{}).get('currency',{})).split('?')[0]
def number(x):return format(b.D(x).normalize(),'f')
def psig(p):
 return {'id':p['id'],'quantity':number(p.get('quantity')),'price':number(p.get('price')),'assortment':m.href(p.get('assortment',{})),'discount':number(p.get('discount')),'vat':number(p.get('vat')),'vatEnabled':p.get('vatEnabled'),'pack':p.get('pack'),'slot':m.href(p.get('slot',{})),'things':p.get('things'),'country':m.href(p.get('country',{})),'gtd':p.get('gtd')}
def signature(d,typ):
 out={'positions':[psig(p) for p in rows(d)],'sum':number(d.get('sum')),'currency':currency(d),'rate':number(d.get('rate',{}).get('value',1)),'applicable':d.get('applicable'),'vatEnabled':d.get('vatEnabled'),'vatIncluded':d.get('vatIncluded'),'overhead':d.get('overhead')}
 if typ in FIN:
  out['vatSum']=number(d.get('vatSum'))
  out['operations']=[{'href':m.href(o).split('?')[0],'linkedSum':number(o.get('linkedSum'))} for o in d.get('operations',[])]
 return out
def prepare(source,typ,cny):
 plan=b.plan(source,rows(source));body={'id':source['id'],'rate':{'currency':m.meta(cny),'value':12}}
 desired=copy.deepcopy(source);desired['rate']=body['rate'];desired['sum']=int(plan['actual_minor'])
 if rows(source):
  body['positions']=[]
  for p,price in zip(rows(source),plan['price_minor']):
   q={k:copy.deepcopy(p[k]) for k in FIELDS if k in p}
   q['assortment']=m.meta(p['assortment']);q['price']=int(price);body['positions'].append(q)
  desired['positions']['rows']=[{**p,'price':q['price']} for p,q in zip(rows(source),body['positions'])]
 if isinstance(source.get('overhead'),dict) and 'sum' in source['overhead']:
  body['overhead']={**copy.deepcopy(source['overhead']),'sum':int(b.R(b.D(source['overhead']['sum'])/12))}
  desired['overhead']=body['overhead']
 if typ in FIN:
  body['sum']=int(b.R(b.D(source['sum'])/12));desired['sum']=body['sum']
  if 'vatSum' in source:body['vatSum']=int(b.R(b.D(source['vatSum'])/12));desired['vatSum']=body['vatSum']
  if 'operations' in source:
   assert all('linkedSum' in o for o in source['operations'])
   oldops=source['operations']
   ops=[{**m.meta(o),'linkedSum':int(b.R(b.D(o['linkedSum'])/12))} for o in oldops]
   allocated=sum((b.D(o['linkedSum']) for o in oldops),Decimal(0))
   target=body['sum']-int(b.R((b.D(source['sum'])-allocated)/12))
   diff=target-sum(o['linkedSum'] for o in ops)
   assert not diff or ops
   if diff:
    order=sorted(range(len(ops)),key=lambda i:b.D(oldops[i]['linkedSum'])/12-b.D(ops[i]['linkedSum']),reverse=diff>0)
    step=1 if diff>0 else -1
    for j in range(abs(diff)):
     i=order[j%len(order)];assert ops[i]['linkedSum']+step>=0;ops[i]['linkedSum']+=step
   body['operations']=ops;desired['operations']=ops
 return body,signature(desired,typ),plan
def live(t,typ,ids):
 page=t.request(m.MS,'entity/'+typ,params={'filter':';'.join('id='+i for i in ids),'limit':100,'expand':'positions'})
 assert page['meta']['size']==len(ids) and {d['id'] for d in page['rows']}==set(ids)
 for d in page['rows']:
  if isinstance(d.get('positions'),dict):
   pp=d['positions'];rr=pp.get('rows',[])
   if len(rr)!=pp['meta']['size']:rr=b.fullrows(t,'entity/'+typ+'/'+d['id']+'/positions')
   d['positions']={**pp,'rows':rr};assert len(rr)==pp['meta']['size']
 return {d['id']:d for d in page['rows']}
def write_once(db,typ,bodies,key):
 headers={'Accept':'application/json;charset=utf-8','Content-Type':'application/json','Accept-Encoding':'gzip','Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN']}
 req=urllib.request.Request(m.MS+'entity/'+typ,data=json.dumps(bodies,ensure_ascii=False).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as response:
   raw=response.read()
   if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   result=json.loads(raw)
  save(db,key+':response',{'received':True,'response':result,'at':m.now()})
 except urllib.error.HTTPError as error:
  raw=error.read()
  try:
   if error.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':error.code}
  save(db,key+':response',{'received':True,'http_status':error.code,'detail':detail,'at':m.now()})
 except (TimeoutError,urllib.error.URLError):
  save(db,key+':response',{'received':False,'uncertain':True,'at':m.now()})
def run(typ,start,end):
 t=b.ReadOnly();db=m.Cache(t);auth=db.get(ROOT+'authorization:v1')
 assert auth and auth['authorized'] and auth['scope']=='all_ms_documents_to_cny'
 assert typ in auth['write_types'] and typ not in auth['deferred_types']
 assert auth['rub_per_cny']==12 and auth['unit_price_decimals']==2
 assert auth['preserve_quantities'] and auth['preserve_position_rows'] and not auth['outside_ms_changes']
 assert db.get(b.ROOT+'verified_plan:v1')['status']=='complete'
 manifest=db.get(b.ROOT+'backup_manifest:v1')
 for group in ('orders','shipments','other'):assert db.get(b.ROOT+'backup_result:'+group)['status']=='complete'
 currencies=b.fullrows(t,'entity/currency');default=next(c for c in currencies if c.get('default'))
 assert default['isoCode']=='RUB'
 cny=[c for c in currencies if c.get('isoCode')=='CNY' and not c.get('archived')];assert len(cny)==1;cny=cny[0]
 rub={m.href(c) for c in currencies if c.get('isoCode')=='RUB'}
 count=next(x['count'] for x in manifest['counts'] if x['type']==typ)
 assert start%100==0 and end%100==0 and start>=0 and end>start
 current_count=t.request(m.MS,'entity/'+typ,params={'limit':1})['meta']['size']
 assert current_count==count,'Document count changed; reconcile newly created/deleted documents'
 completed=0;already=0;deviations=0
 for offset in range(start,min(end,count),100):
  key='batch:'+typ+':'+str(offset)
  prior=db.get(ROOT+key)
  if prior and prior.get('status')=='verified':
   completed+=prior['documents'];already+=prior['already_cny'];deviations+=prior['deviations'];continue
  page=db.get(b.ROOT+'backup:'+typ+':page:'+str(offset))
  source=page['documents'];assert b.digest(source)==page['sha256']
  ids=[d['id'] for d in source];assert len(ids)==len(set(ids))
  before=live(t,typ,ids);bodies=[];plans=[];goals={}
  for old in source:
   assert currency(old) in rub and b.D(old['rate'].get('value',1))==1
   body,goal,plan=prepare(old,typ,cny);fresh=before[old['id']];sig=signature(fresh,typ)
   goals[old['id']]=goal;plans.append({'id':old['id'],'name':old.get('name'),'plan':plan,'expected':goal})
   if sig==goal:already+=1;continue
   if sig!=signature(old,typ):
    save(db,key+':conflict',{'source':old,'fresh':fresh,'expected':goal,'at':m.now()})
    raise m.Stop('Source conflict: inspect private snapshot, do not overwrite')
   bodies.append(body)
  if prior:
   # An earlier uncertain batch may only be finalized by observing every goal.
   assert not bodies,'Prior write intent remains: manual reconciliation required'
  else:
   receipt={'status':'intended','type':typ,'offset':offset,'source_hash':page['sha256'],'live_before':list(before.values()),'bodies':bodies,'plans':plans,'at':m.now()}
   if not db.claim(ROOT+key,receipt):raise m.Stop('Batch already claimed; no concurrent replay')
   if bodies:write_once(db,typ,bodies,key)
  after=live(t,typ,ids)
  for old in source:
   actual=signature(after[old['id']],typ)
   if actual!=goals[old['id']]:
    save(db,key+':mismatch',{'id':old['id'],'after':after[old['id']],'expected':goals[old['id']],'at':m.now()})
    raise m.Stop('Readback mismatch; no further batches written')
   for field in ('name','moment','description','externalCode'):
    assert old.get(field)==after[old['id']].get(field),'Nonmonetary header changed'
   for field in ('agent','organization','store','targetStore','sourceStore','purchaseOrder','customerOrder','demand','supply','contract'):
    assert m.href(old.get(field,{}))==m.href(after[old['id']].get(field,{})),'Relationship changed'
  ndev=sum(b.D(p['plan']['deviation_minor'])!=0 for p in plans);deviations+=ndev;completed+=len(source)
  batch_already=len(source)-len(bodies)
  save(db,key,{'status':'verified','type':typ,'documents':len(source),'written':len(bodies),'already_cny':batch_already,'deviations':ndev,'plans':plans,'after':list(after.values()),'at':m.now()})
  save(db,'progress:'+typ+':'+str(start),{'status':'running','type':typ,'start':start,'end':end,'next_offset':offset+100,'verified_documents':completed,'already_cny':already,'deviation_documents':deviations,'at':m.now()})
 currencies=b.fullrows(t,'entity/currency')
 assert next(c for c in currencies if c.get('default'))['id']==default['id']
 save(db,'result:'+typ+':'+str(start),{'status':'complete','type':typ,'start':start,'end':end,'verified_documents':completed,'already_cny':already,'deviation_documents':deviations,'accounting_currency':'RUB','at':m.now()})
 print('Authorized document section converted and verified; private journal saved.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('type');p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=5000);a=p.parse_args()
 try:run(a.type,a.start,a.end)
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:'+a.type+':'+str(a.start),{'status':'stopped','type':a.type,'start':a.start,'error':type(error).__name__,'detail':str(error),'at':m.now()})
  except Exception:pass
  print('Document section stopped; reconcile private journal before retry.')
  sys.exit(1)
