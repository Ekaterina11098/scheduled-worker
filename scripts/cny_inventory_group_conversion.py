"""Authorized reviewed inventory conversion and linked loss reference normalization."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_incoming_refs_apply as h
import cny_one_inventory_price_conversion as iv
r=h.r;b=h.b;m=h.m;P='inventory_group_conversion:'
def save(db,k,v):b.put(db,P+k,v)
def live(t,typ,ids):
 out={}
 for o in range(0,len(ids),25):out.update(r.live(t,typ,ids[o:o+25]))
 return out
def same(old,new,typ):
 if typ=='inventory':iv.inv(old,new)
 else:
  h.related_inv(old,new)
  assert [r.psig(p) for p in r.rows(old)]==[r.psig(p) for p in r.rows(new)],'Related prices or positions changed'
  assert m.href(old.get('inventory',{}))==m.href(new.get('inventory',{}))
 assert r.signature(old,typ)==r.signature(new,typ),'Document differs from expected snapshot'
def validate_goal(old,new,goal,typ):
 if typ=='inventory':
  iv.inv(old,new)
  for p in r.rows(new):
   assert b.D(p['correctionSum'])==b.R(b.D(p['price'])*b.D(p['correctionAmount'])),'Inventory correction sum mismatch'
 else:
  h.related_inv(old,new)
  assert [r.psig(p) for p in r.rows(old)]==[r.psig(p) for p in r.rows(new)]
  assert m.href(old.get('inventory',{}))==m.href(new.get('inventory',{}))
 assert r.signature(goal,typ)==r.signature(new,typ),'Target readback mismatch; no replay'
def write(db,typ,bodies,key,authorized_ids):
 assert typ in ('inventory','loss') and bodies and len(bodies)<=10
 assert {q['id'] for q in bodies}<=set(authorized_ids)
 for q in bodies:assert set(q)==({'id','positions'} if typ=='inventory' else {'id','rate','positions'})
 assert db.claim(b.ROOT+P+key+':intent',{'at':m.now(),'type':typ,'bodies':bodies}),'Existing mutation intent: reconcile first'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/'+typ,data=json.dumps(bodies).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as response:
   raw=response.read()
   if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,key+':response',{'at':m.now(),'received':True,'data':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   error=json.loads(raw)
  except Exception:error={'status':e.code}
  save(db,key+':response',{'at':m.now(),'http_status':e.code,'detail':error})
 except (TimeoutError,urllib.error.URLError):save(db,key+':response',{'at':m.now(),'uncertain':True})
def inspect(t,db,cfg):
 review=db.get(b.ROOT+'inventory_currency_detail_review:result:v1');assert review['status']=='complete'
 source={}
 for o in range(0,len(cfg['inventory_ids']),25):
  source.update(db.get(b.ROOT+'inventory_currency_detail_review:inventories:'+str(o))['documents'])
 assert set(source)==set(cfg['inventory_ids']) and len(source)==192
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 before={'inventory':live(t,'inventory',sorted(source))};goals={'inventory':{}};bodies={'inventory':{}};plans={};refs={'loss':set(),'enter':set()};records=[]
 for i,old in source.items():
  d=before['inventory'][i];iv.inv(old,d);plan=b.plan(old,r.rows(old))
  goal=copy.deepcopy(old);goal['sum']=int(plan['actual_minor']);body={'id':i,'positions':[]}
  for p,price in zip(r.rows(old),plan['price_minor']):
   q={k:copy.deepcopy(p[k]) for k in ('id','quantity','pack','slot','things') if k in p}
   q['assortment']=m.meta(p['assortment']);q['price']=int(price);body['positions'].append(q)
  assert len(body['positions'])<=1000
  goal['positions']['rows']=[{**p,'price':q['price'],'correctionSum':float(b.R(b.D(q['price'])*b.D(p['correctionAmount'])))} for p,q in zip(r.rows(old),body['positions'])]
  goals['inventory'][i]=goal;plans[i]=plan
  if r.signature(d,'inventory')==r.signature(goal,'inventory'):validate_goal(old,d,goal,'inventory')
  else:
   same(old,d,'inventory');bodies['inventory'][i]=body
  for field in ('losses','enters'):
   for ref in d.get(field,[]):
    typ=ref['meta']['type'];assert typ in refs;refs[typ].add(m.href(ref).split('/')[-1])
  records.append({'id':i,'name':d['name'],'moment':d['moment'],'store_href':m.href(d.get('store',{})),'original_minor':old['sum'],'target_minor':plan['target_minor'],'planned_minor':plan['actual_minor'],'deviation_minor':plan['deviation_minor'],'positions':len(r.rows(d))})
 for typ,ids in refs.items():before[typ]=live(t,typ,sorted(ids))
 original_linked={}
 for typ,n in review['linked_counts'].items():
  original_linked[typ]={}
  for o in range(0,n,50):original_linked[typ].update(db.get(b.ROOT+'inventory_currency_detail_review:linked:'+typ+':'+str(o))['documents'])
 assert set(before['enter'])==set(original_linked['enter']) and set(before['loss'])==set(original_linked['loss'])
 for i,d in before['enter'].items():same(original_linked['enter'][i],d,'enter')
 goals['loss']={};bodies['loss']={}
 for i,d in before['loss'].items():
  old=original_linked['loss'][i];h.related_inv(old,d)
  assert [r.psig(p) for p in r.rows(old)]==[r.psig(p) for p in r.rows(d)] and b.D(old['sum'])==b.D(d['sum'])
  assert m.href(old.get('inventory',{}))==m.href(d.get('inventory',{})) and m.href(d.get('inventory',{})).split('/')[-1] in source
  goal=copy.deepcopy(d);goal['rate']={'currency':m.meta(base),'value':1};goals['loss'][i]=goal
  if r.signature(d,'loss')==r.signature(goal,'loss'):continue
  assert b.D(d['rate'].get('value',1))==12
  assert next(c['isoCode'] for c in cc if m.href(c)==r.currency(d))=='CNY'
  q={'id':i,'rate':goal['rate'],'positions':[]}
  for p in r.rows(d):
   pp={k:copy.deepcopy(p[k]) for k in r.FIELDS if k in p};pp['assortment']=m.meta(p['assortment']);pp['price']=p['price'];q['positions'].append(pp)
  assert len(q['positions'])<=1000;bodies['loss'][i]=q
 wh=h.warehouse(t)
 result={'at':m.now(),'before':before,'goals':goals,'bodies':bodies,'plans':plans,'records':records,'warehouse_before':wh,'currencies':cc,'already_inventory':len(source)-len(bodies['inventory']),'already_loss':len(refs['loss'])-len(bodies['loss'])}
 save(db,'preflight:v1',result);return result
def watch_links(t,pf,chunk):
 refs={'loss':set(),'enter':set()}
 for i in chunk:
  for field in ('losses','enters'):
   for x in pf['before']['inventory'][i].get(field,[]):refs[x['meta']['type']].add(m.href(x).split('/')[-1])
 for typ,ids in refs.items():
  for i,d in live(t,typ,sorted(ids)).items():same(pf['before'][typ][i],d,typ)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'authorization:v1')
 assert cfg['authorized'] and cfg['scope']=='reviewed_inventory_group_and_linked_loss_references'
 assert cfg['rub_per_cny']==12 and cfg['preserve_quantities'] and cfg['preserve_stores'] and cfg['preserve_position_order'] and cfg['nearest_reachable_allowed'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'result:v1'),'Scope already completed'
 pf=db.get(b.ROOT+P+'preflight:v1') or inspect(t,db,cfg)
 wh0=pf['warehouse_before'];assert h.warehouse(t)==wh0,'Warehouse quantities changed since preflight'
 assert h.h.ccstate(pf['currencies'])==h.h.ccstate(b.fullrows(t,'entity/currency'))
 counts={'inventory':0,'loss':0}
 for typ in ('inventory','loss'):
  ids=sorted(pf['bodies'][typ])
  for o in range(0,len(ids),10):
   chunk=ids[o:o+10];key='batch:'+typ+':'+str(o)
   current=live(t,typ,chunk);intent=db.get(b.ROOT+P+key+':intent')
   if intent:
    for i,d in current.items():validate_goal(pf['before'][typ][i],d,pf['goals'][typ][i],typ)
   else:
    for i,d in current.items():same(pf['before'][typ][i],d,typ)
    assert h.warehouse(t)==wh0,'Warehouse quantities changed before batch'
    if typ=='inventory':watch_links(t,pf,chunk)
    else:
     inv_ids=sorted({m.href(d['inventory']).split('/')[-1] for d in current.values()})
     for i,d in live(t,'inventory',inv_ids).items():validate_goal(pf['before']['inventory'][i],d,pf['goals']['inventory'][i],'inventory')
    save(db,key+':before',{'at':m.now(),'documents':current})
    write(db,typ,[pf['bodies'][typ][i] for i in chunk],key,ids)
    for attempt in range(13):
     current=live(t,typ,chunk)
     if all(r.signature(d,typ)==r.signature(pf['goals'][typ][i],typ) for i,d in current.items()):break
     if attempt<12:time.sleep(15)
    save(db,key+':readback',{'at':m.now(),'documents':current})
    for i,d in current.items():validate_goal(pf['before'][typ][i],d,pf['goals'][typ][i],typ)
   if typ=='inventory':watch_links(t,pf,chunk)
   assert h.warehouse(t)==wh0,'Warehouse quantity mismatch after batch'
   save(db,key+':result',{'at':m.now(),'status':'verified','documents':len(chunk),'quantity_fields_stores_order_preserved':True})
   counts[typ]+=len(chunk)
   save(db,'progress:v1',{'at':m.now(),'status':'running','stage':typ,'verified':counts,'already_inventory':pf['already_inventory'],'already_loss':pf['already_loss']})
  # Validate the whole completed stage before advancing.
  stage=live(t,typ,sorted(pf['goals'][typ]))
  for i,d in stage.items():validate_goal(pf['before'][typ][i],d,pf['goals'][typ][i],typ)
  save(db,'stage:'+typ+':verified',{'at':m.now(),'status':'verified','documents':len(stage)})
 final={}
 for typ in ('inventory','loss','enter'):
  final[typ]=live(t,typ,sorted(pf['before'][typ]))
  for i,d in final[typ].items():
   if typ=='enter':same(pf['before'][typ][i],d,typ)
   else:validate_goal(pf['before'][typ][i],d,pf['goals'][typ][i],typ)
  for o in range(0,len(final[typ]),25):
   kk=list(final[typ])[o:o+25];save(db,'final:'+typ+':'+str(o),{'at':m.now(),'documents':{i:final[typ][i] for i in kk}})
 wh1=h.warehouse(t);assert wh1==wh0
 assert h.h.ccstate(pf['currencies'])==h.h.ccstate(b.fullrows(t,'entity/currency'))
 for x in pf['records']:x['after_minor']=final['inventory'][x['id']]['sum']
 save(db,'result:v1',{'status':'verified','at':m.now(),'written':counts,'already_inventory':pf['already_inventory'],'already_loss':pf['already_loss'],'inventories':len(final['inventory']),'losses':len(final['loss']),'enters_verified_unchanged':len(final['enter']),'records':pf['records'],'loss_records':[{'id':i,'name':d['name'],'sum_minor':d['sum']} for i,d in final['loss'].items()],'all_store_quantities_preserved':True,'all_inventory_quantity_fields_preserved':True,'stores_positions_order_preserved':True,'loss_prices_sums_preserved':True,'warehouse_before':wh0,'warehouse_after':wh1,'currency_settings_unchanged':True,'outside_ms_changes':False})
 print('Inventory group and linked loss currency references verified; all stock quantities and stores preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Inventory group correction stopped; reconcile private checkpoints before further writes.');sys.exit(1)
