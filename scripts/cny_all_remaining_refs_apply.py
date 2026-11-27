"""Narrow, checkpointed reference-only normalization; no price conversion."""
import argparse,copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_all_remaining_refs_preflight as p
h=p.h;r=p.r;b=p.b;m=p.m;P=p.P
FIN={'paymentin','paymentout','cashin','cashout'}
WRITABLE={'customerorder','demand','invoicein','loss','move','paymentin','paymentout','cashout','purchaseorder','purchasereturn','salesreturn','supply','enter','invoiceout','cashin'}
def save(db,k,v):p.save(db,k,v)
def refs(d,k):return sorted(m.href(x).split('?')[0] for x in d.get(k,[]))
def signature(d,typ):
 s=r.signature(d,typ)
 if typ in FIN:
  s['vatSum']=r.number(d.get('vatSum'))
  s['operations']=sorted((m.href(x).split('?')[0],r.number(x.get('linkedSum'))) for x in d.get('operations',[]))
 return s
def invariant(a,z,typ):
 assert [r.psig(x) for x in r.rows(a)]==[r.psig(x) for x in r.rows(z)],'Prices, quantities or row order changed'
 for x,y in zip(r.rows(a),r.rows(z)):
  for k in ('reserve','wait','shipped','received','inTransit','trackingCodes','trackingCodes_1162','customsDeclarationNumber'):
   assert x.get(k)==y.get(k),'Position detail changed: '+k
 assert b.D(a.get('sum'))==b.D(z.get('sum')),'Nominal total changed'
 for k in ('id','name','moment','description','applicable','externalCode','vatEnabled','vatIncluded','reserve','overhead','attributes','syncId','code','shared','printed','published'):
  assert a.get(k)==z.get(k),'Header changed: '+k
 for k in ('demand','customerOrder','purchaseOrder','supply','agent','organization','store','sourceStore','targetStore','contract','project','state','organizationAccount','agentAccount','salesChannel','owner','group','invoiceIn','invoiceOut'):
  assert m.href(a.get(k,{}))==m.href(z.get(k,{})),'Document or warehouse reference changed: '+k
 for k in ('returns','payments','demands','losses','supplies','moves','invoicesIn','invoicesOut'):
  assert refs(a,k)==refs(z,k),'Related document set changed: '+k
 if typ in FIN:
  assert signature(a,typ)['operations']==signature(z,typ)['operations'],'Payment allocations changed'
  assert b.D(a.get('vatSum'))==b.D(z.get('vatSum')),'Payment VAT changed'
def body(d,base,typ):
 q={'id':d['id'],'rate':{'currency':m.meta(base),'value':1}}
 if isinstance(d.get('positions'),dict):
  q['positions']=[]
  for row in r.rows(d):
   pp={k:copy.deepcopy(row[k]) for k in r.FIELDS if k in row}
   pp['assortment']=m.meta(row['assortment']);pp['price']=row['price'];q['positions'].append(pp)
 if typ in FIN:
  q['sum']=d['sum']
  if 'vatSum' in d:q['vatSum']=d['vatSum']
  if 'operations' in d:
   assert all('linkedSum' in x for x in d['operations'])
   q['operations']=[{**m.meta(x),'linkedSum':x['linkedSum']} for x in d['operations']]
 if d.get('overhead') is not None:q['overhead']=copy.deepcopy(d['overhead'])
 return q
def write(db,typ,bodies,key):
 assert typ in WRITABLE and 0<len(bodies)<=100
 assert all(set(q)<={'id','rate','positions','sum','vatSum','operations','overhead'} for q in bodies)
 assert db.claim(b.ROOT+P+key+':intent',{'at':m.now(),'type':typ,'bodies':bodies}),'Existing intent: reconcile, never replay'
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
def run(typ,start,end,batch_size=20):
 t=b.ReadOnly();db=m.Cache(t);auth=db.get(b.ROOT+P+'authorization:v1');pf=db.get(b.ROOT+P+'preflight:v1');initial=db.get(b.ROOT+P+'start:v1')
 assert auth and auth['authorized'] and auth['scope']=='remaining_ms_currency_references_only'
 assert auth['preserve_prices_sums_quantities_rows_stores_documents'] and not auth['outside_ms_changes']
 assert pf['status']=='complete' and not pf['errors'] and pf['warehouse_quantities_unchanged']
 assert not any(s['issues'] for s in pf['types']),'Unexpected currencies require review'
 cc=b.fullrows(t,'entity/currency');assert h.h.ccstate(cc)==h.h.ccstate(initial['currencies'])
 base=next(c for c in cc if c.get('default'));assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 iso={m.href(c):c.get('isoCode') for c in cc}
 info=db.get(b.ROOT+P+'type:'+typ);ids=info['candidates']
 assert typ in WRITABLE and start>=0 and end>start and start%20==0 and end%20==0
 # The current warehouse map is rechecked before the first write and after this section.
 wh0=h.warehouse(t);assert wh0==initial['warehouse_quantities'],'Warehouse changed since inventory; reconcile before writing'
 baseline={}
 selected=set(ids[start:min(end,len(ids))])
 header_pages=sorted({(j//1000)*1000 for j,i in enumerate(info['ids']) if i in selected})
 for o in header_pages:
  for d in db.get(b.ROOT+P+'headers:'+typ+':'+str(o))['documents']:baseline[d['id']]=d
 verified=written=0
 assert batch_size in (20,100)
 for off in range(start,min(end,len(ids)),batch_size):
  chunk=ids[off:min(off+batch_size,end)];key='apply:'+typ+':'+str(off)
  snapshot=db.get(b.ROOT+P+key+':snapshot');intent=db.get(b.ROOT+P+key+':intent')
  current=r.live(t,typ,chunk)
  if snapshot:
   assert intent,'Snapshot without intent requires reconciliation'
   before=snapshot['before'];goals=snapshot['goals']
   for i,z in current.items():
    invariant(before[i],z,typ);assert signature(z,typ)==signature(goals[i],typ),'Prior mutation unresolved; no replay'
   save(db,key+':verified',{'at':m.now(),'count':len(chunk),'reconciled':True})
   written+=len(snapshot['bodies'])
  else:
   assert not intent,'Intent without snapshot'
   before=current;goals={};bodies=[]
   for i,d in before.items():
    old=baseline[i]
    for k in ('name','moment','applicable','sum'):
     assert old.get(k)==d.get(k),'Concurrent document edit since inventory: '+k
    assert r.currency(d)==r.currency(old) and b.D(d['rate'].get('value',1))==b.D(old['rate'].get('value',1)),'Reference changed since preflight'
    assert iso[r.currency(d)]=='CNY' and b.D(d['rate'].get('value',1)) in (1,12)
    q=body(d,base,typ);g=copy.deepcopy(d);g['rate']=q['rate'];goals[i]=g;bodies.append(q)
   assert all(q['id'] in before for q in bodies)
   save(db,key+':snapshot',{'at':m.now(),'before':before,'goals':goals,'bodies':bodies})
   write(db,typ,bodies,key)
   for attempt in range(13):
    after=r.live(t,typ,chunk)
    if all(signature(after[i],typ)==signature(goals[i],typ) for i in chunk):break
    if attempt<12:time.sleep(15)
   save(db,key+':readback',{'at':m.now(),'documents':after})
   for i,z in after.items():
    invariant(before[i],z,typ)
    assert signature(z,typ)==signature(goals[i],typ),'Saved monetary state differs from reference-only target; stopped'
   save(db,key+':verified',{'at':m.now(),'count':len(chunk),'prices_sums_quantities_rows_stores_links_preserved':True})
   written+=len(bodies)
  verified+=len(chunk)
  save(db,'apply_progress:'+typ+':'+str(start),{'status':'running','at':m.now(),'type':typ,'start':start,'next_offset':off+len(chunk),'verified':verified,'written':written,'total_candidates':len(ids)})
  if verified%1000==0:assert h.warehouse(t)==wh0,'Warehouse changed during correction; stop and reconcile'
 assert h.warehouse(t)==wh0,'Warehouse changed during section'
 assert h.h.ccstate(b.fullrows(t,'entity/currency'))==h.h.ccstate(cc)
 save(db,'section:'+typ+':'+str(start),{'status':'verified','at':m.now(),'type':typ,'start':start,'end':end,'verified':verified,'written':written,'all_store_quantities_preserved':True})
 print('Reference-only section verified; quantities, prices and nominal totals preserved.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('type');ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=1000);ap.add_argument('--batch-size',type=int,default=20);args=ap.parse_args()
 try:run(args.type,args.start,args.end,args.batch_size)
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:apply:'+args.type+':'+str(args.start),{'at':m.now(),'reason':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Reference correction stopped; reconcile private checkpoint before further writes.');sys.exit(1)
