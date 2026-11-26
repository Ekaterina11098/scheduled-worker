"""Authorized incoming currency reference normalization; immutable stock quantities."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_one_chain_align_test as a
import cny_gray_umbrella_cost_apply as h
r=a.r;b=a.b;m=a.m;P='incoming_cost_refs_all:'
def save(db,k,v):b.put(db,P+k,v)
def warehouse(t):
 rows=h.bystore(t)
 return {m.href(d).split('?')[0]:{m.href(x).split('?')[0]:r.number(x['stock']) for x in d['stockByStore']} for d in rows}
def read_docs(t,pf,db):
 docs={}
 for typ,ss in pf['summary'].items():
  docs[typ]={}
  for o in ss['pages']:docs[typ].update(db.get(b.ROOT+P+'preflight:'+typ+':'+str(o))['documents'])
 return docs
def write(db,typ,bodies,key):
 assert all(set(q)<= {'id','rate','positions','overhead'} and set(q)>={'id','rate','positions'} for q in bodies)
 assert db.claim(b.ROOT+P+key+':intent',{'at':m.now(),'type':typ,'bodies':bodies}),'Existing write intent; reconcile first'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/'+typ,data=json.dumps(bodies).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,key+':response',{'at':m.now(),'received':True,'data':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'status':e.code}
  save(db,key+':response',{'at':m.now(),'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,key+':response',{'at':m.now(),'uncertain':True})
def main():
 t=b.ReadOnly();db=m.Cache(t);auth=db.get(b.ROOT+P+'authorization:v1')
 assert auth['authorized'] and auth['preserve_quantities'] and not auth['outside_ms_changes'] and auth['rub_per_cny']==12
 pf=db.get(b.ROOT+P+'preflight:v1');assert pf['status']=='complete'
 assert not pf['issues'],'Preflight issues require resolution before any mutation'
 assert not db.get(b.ROOT+P+'apply_started:v1'),'Prior execution; reconcile journal before replay'
 docs=read_docs(t,pf,db);cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['id']==pf['base']['id'] and base['isoCode']=='CNY' and b.D(base['rate'])==1
 wh0=warehouse(t);save(db,'apply_started:v1',{'at':m.now(),'warehouse_quantities':wh0,'currencies':cc})
 counts={};done=0
 for typ,ss in pf['summary'].items():
  heads=b.fullrows(t,'entity/'+typ);assert {d['id'] for d in heads}==set(docs[typ]),'Incoming document set changed'
  ids=ss['ready'];counts[typ]=0
  for o in range(0,len(ids),25):
   chunk=ids[o:o+25];key='batch:'+typ+':'+str(o)
   before=r.live(t,typ,chunk);goals={};bodies=[]
   for i,d in before.items():
    old=docs[typ][i];h.inv(old,d);assert r.signature(old,typ)==r.signature(d,typ),'Concurrent incoming edit'
    assert b.D(d['rate'].get('value',1))==12
    q={'id':i,'rate':{'currency':m.meta(base),'value':1},'positions':[]}
    for p in r.rows(d):
     pp={k:copy.deepcopy(p[k]) for k in r.FIELDS if k in p}
     pp['assortment']=m.meta(p['assortment']);pp['price']=p['price'];q['positions'].append(pp)
    if d.get('overhead') is not None:q['overhead']=copy.deepcopy(d['overhead'])
    g=copy.deepcopy(d);g['rate']=q['rate'];goals[i]=g;bodies.append(q)
   # Monetary signatures of attached payments and orders are read but never written.
   related={}
   for d in before.values():
    refs=list(d.get('payments',[]))+([d['purchaseOrder']] if d.get('purchaseOrder') else [])
    for x in refs:
     href=m.href(x).split('?')[0];rt=x['meta']['type'];ri=href.split('/')[-1]
     assert rt in ('paymentout','cashout','purchaseorder')
     related.setdefault(rt,set()).add(ri)
   linked={}
   for rt,ri in related.items():
    linked[rt]={}
    for z in range(0,len(ri),50):linked[rt].update(r.live(t,rt,sorted(ri)[z:z+50]))
   assert warehouse(t)==wh0,'Warehouse quantities changed before write; stop'
   save(db,key+':snapshot',{'at':m.now(),'before':before,'goals':goals,'linked_before':linked})
   write(db,typ,bodies,key)
   for attempt in range(13):
    after=r.live(t,typ,chunk)
    if all(r.signature(after[i],typ)==r.signature(goals[i],typ) for i in chunk):break
    if attempt<12:time.sleep(15)
   save(db,key+':readback',{'at':m.now(),'after':after})
   for i,d in after.items():h.inv(before[i],d);assert r.signature(d,typ)==r.signature(goals[i],typ),'Readback mismatch; no replay'
   for rt,oldset in linked.items():
    newset=r.live(t,rt,list(oldset)) if len(oldset)<=100 else {}
    if not newset:
     for z in range(0,len(oldset),50):newset.update(r.live(t,rt,list(oldset)[z:z+50]))
    for i,d in newset.items():
     a.invariants(oldset[i],d);assert r.signature(oldset[i],rt)==r.signature(d,rt),'Related document monetary values changed'
   wh=warehouse(t);assert wh==wh0,'Warehouse quantities mismatch after batch'
   save(db,key+':result',{'status':'verified','at':m.now(),'documents':len(chunk),'positions':sum(len(r.rows(d)) for d in before.values()),'all_quantities_preserved':True,'prices_rows_order_preserved':True,'linked_documents_preserved':True})
   counts[typ]+=len(chunk);done+=len(chunk)
   save(db,'apply_progress:v1',{'status':'running','at':m.now(),'verified':done,'counts':counts,'type':typ,'next_offset':o+len(chunk)})
 # Re-read every incoming document, including already corrected records.
 for typ,ss in pf['summary'].items():
  ids=list(docs[typ])
  for o in range(0,len(ids),50):
   current=r.live(t,typ,ids[o:o+50])
   for i,d in current.items():
    h.inv(docs[typ][i],d)
    goal=copy.deepcopy(docs[typ][i]);goal['rate']={'currency':m.meta(base),'value':1}
    assert r.signature(d,typ)==r.signature(goal,typ),'Final incoming reference mismatch'
   save(db,'final:'+typ+':'+str(o),{'at':m.now(),'documents':current})
 wh1=warehouse(t);assert wh1==wh0
 assert h.ccstate(cc)==h.ccstate(b.fullrows(t,'entity/currency'))
 costs=b.fullrows(t,'report/stock/all',{'filter':'stockMode=all;quantityMode=all'})
 for o in range(0,len(costs),100):save(db,'after:costs:'+str(o),{'at':m.now(),'rows':costs[o:o+100]})
 save(db,'after:costs:manifest',{'count':len(costs),'pages':list(range(0,len(costs),100))})
 save(db,'result:v1',{'status':'verified','at':m.now(),'counts':counts,'written':done,'already_correct':sum(len(s['already']) for s in pf['summary'].values()),'all_store_quantities_preserved':True,'all_prices_rows_order_preserved':True,'incoming_currency_references_verified':True,'currency_settings_unchanged':True,'warehouse_quantities_before':wh0,'warehouse_quantities_after':wh1,'outside_ms_changes':False,'cost_report_rows':len(costs)})
 print('Incoming currency references verified; prices and all warehouse quantities preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:apply:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Incoming correction stopped; reconcile private checkpoints before further writes.');sys.exit(1)
