"""Scoped order-price alignment for a frozen set of remaining return chains."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_one_chain_align_test as a
s=a.s;r=a.r;b=a.b;m=a.m
P='returns_simple_align_clear:'
TYPES=('customerorder','demand','salesreturn','paymentin','paymentout')
WRITE=('demand','salesreturn','paymentin','paymentout')
def save(db,k,v):b.put(db,P+k,v)
def live(t,originals):
 out={}
 for typ in TYPES:
  ids=list(originals.get(typ,{}))
  if ids:out[typ]=r.live(t,typ,ids)
 return out
def flatten(chains):
 out={}
 for chain in chains:
  for typ,d in chain['before'].items():
   assert d['id'] not in out.setdefault(typ,{}),'Shared document requires separate handling'
   out[typ][d['id']]=d
 return out
def invariant(old,new):
 a.invariants(old,new)
 assert r.currency(old)==r.currency(new) and b.D(old['rate'].get('value',1))==b.D(new['rate'].get('value',1)),'Rate or currency changed'
 for k in ('operations',):
  assert [m.href(x) for x in old.get(k,[])]==[m.href(x) for x in new.get(k,[])],'Allocation link changed'
def sigs(docs):
 return {typ:{i:r.signature(d,typ) for i,d in dd.items()} for typ,dd in docs.items()}
def prepare(db,t,cfg,groups):
 currencies=b.fullrows(t,'entity/currency');cny={m.href(c) for c in currencies if c.get('isoCode')=='CNY'}
 assert next(c for c in currencies if c.get('default'))['isoCode']=='CNY'
 conflicts=[];done=0
 for batch,chains in enumerate(groups):
  original=flatten(chains)
  checkpoint=db.get(cfg['source_inspection_prefix']+str(batch));assert checkpoint
  observed=checkpoint['documents']
  before={typ:{i:observed[typ][i] for i in dd} for typ,dd in original.items()}
  save(db,'inspection:'+str(batch),{'at':m.now(),'documents':before})
  goals=copy.deepcopy(before);bodies={typ:[] for typ in WRITE};summaries=[]
  for chain in chains:
   rid=chain['return_id'];old=chain['before']
   try:
    cur={typ:before[typ][d['id']] for typ,d in old.items()}
    assert set(old)>=set(('customerorder','demand','salesreturn'))
    for typ,d in cur.items():
     assert r.currency(d) in cny
     invariant(old[typ],d)
     assert r.signature(d,typ)==r.signature(old[typ],typ),'Document changed after the audit snapshot'
     if typ in ('customerorder','demand','salesreturn'):
      assert len(r.rows(d))==1 and b.D(r.rows(d)[0]['quantity'])==1
      assert b.D(r.rows(d)[0].get('discount'))==0 and b.D(r.rows(d)[0].get('vat'))==0
     else:
      assert b.D(d.get('vatSum'))==0
      assert len(d.get('operations',[]))==1
      assert b.D(d['operations'][0]['linkedSum'])==b.D(d['sum']),'Unallocated payment requires separate review'
    order=cur['customerorder'];demand=cur['demand'];ret=cur['salesreturn']
    target=int(order['sum']);assert b.D(order['sum'])==target and target>=0
    product=m.href(r.rows(order)[0]['assortment'])
    assert all(m.href(r.rows(cur[k])[0]['assortment'])==product for k in ('demand','salesreturn'))
    assert m.href(demand['customerOrder'])==m.MS+'entity/customerorder/'+order['id']
    assert m.href(ret['demand'])==m.MS+'entity/demand/'+demand['id']
    assert [m.href(x) for x in demand.get('returns',[])]==[m.MS+'entity/salesreturn/'+rid]
    assert not order.get('payments'),'Payment linked directly to order requires review'
    for typ,basis in (('paymentin','demand'),('paymentout','salesreturn')):
     links=cur[basis].get('payments',[])
     if typ in cur:
      pay=cur[typ]
      assert len(links)==1 and m.href(links[0])==m.MS+'entity/'+typ+'/'+pay['id']
      assert m.href(pay['operations'][0])==m.MS+'entity/'+basis+'/'+cur[basis]['id']
     else:assert not links,'Unexpected additional payment'
    for typ in WRITE:
     if typ not in cur:continue
     d=cur[typ];goal=goals[typ][d['id']];goal['sum']=target
     if typ in ('demand','salesreturn'):
      oldp=r.rows(d)[0];p={k:copy.deepcopy(oldp[k]) for k in r.FIELDS if k in oldp}
      p['assortment']=m.meta(oldp['assortment']);p['price']=target
      body={'id':d['id'],'positions':[p]}
      goal['positions']['rows'][0]['price']=target
     else:
      op={**m.meta(d['operations'][0]),'linkedSum':target}
      body={'id':d['id'],'sum':target,'operations':[op]};goal['operations']=[op]
     if r.signature(d,typ)!=r.signature(goal,typ):bodies[typ].append(body)
    summaries.append({'return_id':rid,'return_name':ret['name'],'order_id':order['id'],'target_minor':target,'document_ids':{k:d['id'] for k,d in cur.items()}})
   except Exception as error:conflicts.append({'return_id':rid,'detail':str(error),'trace':traceback.format_exc()})
  if not conflicts:
   save(db,'plan:'+str(batch),{'status':'prepared','before':before,'goals':goals,'bodies':bodies,'chains':summaries,'at':m.now()})
  done+=len(chains)
  save(db,'preflight_progress:v1',{'status':'reading','checked_chains':done,'conflicts':len(conflicts),'at':m.now()})
 save(db,'preflight:v1',{'status':'complete' if not conflicts else 'conflicts','chains':done,'conflicts':conflicts,'at':m.now(),'ms_writes':0})
 assert not conflicts,'Preflight conflicts; live MS unchanged'
def write(db,typ,bodies,key,allowed):
 assert typ in WRITE and len(bodies)<=50 and all(x['id'] in allowed for x in bodies)
 assert all(set(x)<=({'id','positions'} if typ in ('demand','salesreturn') else {'id','sum','operations'}) for x in bodies)
 if not db.claim(b.ROOT+P+key,{'status':'intended','at':m.now(),'type':typ,'bodies':bodies}):return
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/'+typ,data=json.dumps(bodies,ensure_ascii=False).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as response:
   raw=response.read()
   if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,key+':response',{'received':True,'at':m.now(),'response':value})
 except urllib.error.HTTPError as error:
  raw=error.read()
  try:
   if error.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':error.code}
  save(db,key+':response',{'received':True,'at':m.now(),'http_status':error.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):
  save(db,key+':response',{'received':False,'uncertain':True,'at':m.now()})
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'scope:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='approved_simple_full_single_item_returns'
 assert cfg['expected_chains']>0 and cfg['max_batch']==50 and cfg['preserve_rates'] and cfg['preserve_quantities'] and cfg['preserve_position_order'] and not cfg['outside_ms_changes']
 parent=db.get(cfg['parent_preflight_key'])
 assert parent and parent['status']=='conflicts' and parent['chains']==cfg['expected_chains']+len(cfg['excluded_return_ids'])
 assert {x['return_id'] for x in parent['conflicts']}==set(cfg['excluded_return_ids']),'Unexpected parent conflict requires review'
 groups=[db.get(b.ROOT+P+'sources:'+str(i))['chains'] for i in range(cfg['source_groups'])]
 allchains=[x for group in groups for x in group]
 assert len(allchains)==cfg['expected_chains'] and {x['return_id'] for x in allchains}=={x['return_id'] for x in cfg['items']}
 alloriginal=flatten(allchains)
 assert len(alloriginal['customerorder'])==len(alloriginal['demand'])==len(alloriginal['salesreturn'])==cfg['expected_chains']
 pre=db.get(b.ROOT+P+'preflight:v1')
 if not pre or pre.get('status')!='complete':prepare(db,t,cfg,groups)
 completed=0
 for batch,chains in enumerate(groups):
  plan=db.get(b.ROOT+P+'plan:'+str(batch));assert plan and plan['status']=='prepared'
  before=plan['before'];goals=plan['goals']
  for typ in WRITE:
   if typ not in before:continue
   stage='stage:'+str(batch)+':'+typ;prior=db.get(b.ROOT+P+stage+':verified')
   if prior:continue
   if not plan['bodies'][typ]:
    save(db,stage+':verified',{'status':'verified','at':m.now(),'type':typ,'documents':len(before[typ]),'written':0,'unchanged_in_preflight':True})
    continue
   checktypes={k:before[k] for k in set(('customerorder',typ,'demand')) if k in before}
   fresh=live(t,checktypes)
   for k,dd in fresh.items():
    for i,d in dd.items():
     invariant(before[k][i],d)
     expected=goals[k][i] if k=='demand' and typ!='demand' else before[k][i]
     if k==typ and db.get(b.ROOT+P+stage):expected=goals[k][i]
     assert r.signature(d,k)==r.signature(expected,k),'Concurrent edit or uncertain write; reconcile before continuing'
   bodies=plan['bodies'][typ]
   if bodies:write(db,typ,bodies,stage,set(before[typ]))
   for attempt in range(13):
    after=r.live(t,typ,list(before[typ]))
    if all(r.signature(d,typ)==r.signature(goals[typ][i],typ) for i,d in after.items()):break
    if attempt<12:time.sleep(15)
   save(db,stage+':readback',{'at':m.now(),'documents':after})
   for i,d in after.items():
    invariant(before[typ][i],d)
    assert r.signature(d,typ)==r.signature(goals[typ][i],typ),'Stage target mismatch; stop without replay'
   save(db,stage+':verified',{'status':'verified','at':m.now(),'type':typ,'documents':len(after),'written':len(bodies)})
   save(db,'progress:v1',{'status':'running','batch':batch,'last_stage':typ,'verified_chains':completed,'at':m.now()})
  final=live(t,before)
  for typ,dd in final.items():
   for i,d in dd.items():
    invariant(before[typ][i],d)
    assert r.signature(d,typ)==r.signature(goals[typ][i],typ),'Chain final reconciliation mismatch'
  save(db,'batch:'+str(batch)+':verified',{'status':'verified','at':m.now(),'chains':plan['chains'],'documents':final})
  completed+=len(chains)
  save(db,'progress:v1',{'status':'running','verified_chains':completed,'batch':batch,'at':m.now()})
 # Independent complete readback after all stages; rates remain unchanged by design.
 totals={};verified=0
 for batch,chains in enumerate(groups):
  plan=db.get(b.ROOT+P+'plan:'+str(batch));final=live(t,plan['before'])
  for typ,dd in final.items():
   totals[typ]=totals.get(typ,0)+len(dd)
   for i,d in dd.items():
    invariant(plan['before'][typ][i],d)
    assert r.signature(d,typ)==r.signature(plan['goals'][typ][i],typ),'Full final reconciliation mismatch'
  verified+=len(chains)
  save(db,'final_audit:'+str(batch),{'status':'verified','at':m.now(),'documents':final})
 save(db,'result:v1',{'status':'verified','at':m.now(),'verified_chains':verified,'documents':totals,'order_prices_source':True,'quantities_order_links_preserved':True,'rates_preserved':True,'global_currency_migration_enabled':False})
 print('Scoped return-chain alignment and complete readback verified; private results saved.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error),'trace':traceback.format_exc()})
  except Exception:pass
  print('Scoped return alignment stopped; inspect private journal before continuing.');sys.exit(1)
