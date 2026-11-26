"""Checkpointed base-CNY normalization of approved equal-nominal chains."""
import copy,gzip,json,os,sys,traceback,urllib.request,urllib.error
import cny_refund_reference_preflight as p
a=p.a;r=p.r;b=p.b;m=p.m;P=p.P
WRITE=('customerorder','demand','paymentin','paymentout')
def save(db,k,v):p.save(db,k,v)
def flatten(chains):
 out={k:{} for k in p.TYPES}
 for ch in chains:
  for typ,d in ch['before'].items():
   assert d['id'] not in out[typ];out[typ][d['id']]=d
 return out
def live(t,docs):
 return {typ:r.live(t,typ,list(dd)) for typ,dd in docs.items() if dd}
def same(x,y,typ):return r.signature(x,typ)==r.signature(y,typ)
def invariant(old,new):
 a.invariants(old,new)
 assert [r.psig(x) for x in r.rows(old)]==[r.psig(x) for x in r.rows(new)]
 assert b.D(old['sum'])==b.D(new['sum'])
 assert [m.href(x) for x in old.get('operations',[])]==[m.href(x) for x in new.get('operations',[])]
def ccstate(cc):return sorted([{k:c.get(k) for k in ('id','isoCode','rate','default','multiplicity','indirect','archived','name')} for c in cc],key=lambda c:c['id'])
def body(old,base,typ):
 q={'id':old['id'],'rate':{'currency':m.meta(base),'value':1}}
 if typ in ('customerorder','demand'):
  q['positions']=[]
  for row in r.rows(old):
   pp={k:copy.deepcopy(row[k]) for k in r.FIELDS if k in row}
   pp['assortment']=m.meta(row['assortment']);pp['price']=row['price'];q['positions'].append(pp)
 else:q.update(sum=old['sum'],operations=[{**m.meta(o),'linkedSum':o['linkedSum']} for o in old['operations']])
 if isinstance(old.get('overhead'),dict):q['overhead']=copy.deepcopy(old['overhead'])
 return q
def write(db,typ,bodies,label,allowed):
 assert typ in WRITE and 0<len(bodies)<=20 and all(x['id'] in allowed for x in bodies)
 assert db.claim(b.ROOT+P+label,{'status':'intended','at':m.now(),'type':typ,'bodies':bodies}),'Existing intent; reconcile before replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/'+typ,data=json.dumps(bodies).encode(),headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=120) as response:
   raw=response.read()
   if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,label+':response',{'at':m.now(),'received':True,'documents':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':e.code}
  save(db,label+':response',{'at':m.now(),'received':True,'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,label+':response',{'at':m.now(),'received':False,'uncertain':True})
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1');pf=db.get(b.ROOT+P+'preflight:v1')
 assert cfg and cfg['authorized'] and cfg['mode']=='apply' and cfg['scope']=='approved_same_nominal_refund_chains_to_base_cny'
 assert cfg['expected_safe_cases']==pf['safe_cases']==155 and not cfg['outside_ms_changes']
 groups=[db.get(b.ROOT+P+'sources:'+str(i))['chains'] for i in range(pf['source_groups'])]
 assert sum(map(len,groups))==155
 all_docs=flatten([c for g in groups for c in g])
 for g in groups:
  for c in g:
   d=c['before']['demand'];o=c['before']['customerorder']
   assert [p.ident(x,'demand') for x in o['demands']]==[d['id']],'Order shared with other demands'
 cc=b.fullrows(t,'entity/currency');assert ccstate(cc)==ccstate(pf['currencies'])
 base=next(c for c in cc if c.get('default'));assert base['id']==cfg['base_currency_id'] and base['isoCode']=='CNY'
 done=0
 for batch,chains in enumerate(groups):
  before=flatten(chains);goals=copy.deepcopy(before)
  for typ in WRITE:
   for d in goals[typ].values():d['rate']={'currency':m.meta(base),'value':1}
  expected=copy.deepcopy(before)
  for typ in WRITE:
   label='apply:'+str(batch)+':'+typ
   prior=db.get(b.ROOT+P+label+':verified')
   if prior:
    expected[typ]=goals[typ];continue
   fresh=live(t,before)
   for k,dd in fresh.items():
    for i,d in dd.items():
     invariant(before[k][i],d)
     assert same(expected[k][i],d,k),'Concurrent edit or uncertain prior mutation'
   bodies=[body(d,base,typ) for i,d in before[typ].items() if not same(d,goals[typ][i],typ)]
   if bodies:write(db,typ,bodies,label,set(before[typ]))
   after=live(t,before);save(db,label+':readback',{'at':m.now(),'documents':after})
   expected[typ]=goals[typ]
   for k,dd in after.items():
    for i,d in dd.items():
     invariant(before[k][i],d);assert same(expected[k][i],d,k),'Readback target mismatch; stop without replay'
   save(db,label+':verified',{'status':'verified','at':m.now(),'written':len(bodies),'type':typ})
   save(db,'progress:apply:v1',{'at':m.now(),'batch':batch,'last_type':typ,'verified_cases':done})
  final=live(t,before)
  for ch in chains:
   target=b.D(ch['before']['salesreturn']['sum'])
   for typ,old in ch['before'].items():
    d=final[typ][old['id']];invariant(old,d);assert same(goals[typ][old['id']],d,typ)
    if typ in ('customerorder','demand','salesreturn'):assert b.D(d['payedSum'])==target
    else:assert b.D(d['operations'][0]['linkedSum'])==target
  save(db,'batch:'+str(batch)+':verified',{'status':'verified','at':m.now(),'documents':final,'cases':len(chains)})
  done+=len(chains);save(db,'progress:apply:v1',{'at':m.now(),'batch':batch,'verified_cases':done})
 totals={};checked=0
 for batch,chains in enumerate(groups):
  before=flatten(chains);final=live(t,before)
  for typ,dd in final.items():
   totals[typ]=totals.get(typ,0)+len(dd)
   for i,d in dd.items():
    old=before[typ][i];invariant(old,d)
    goal=copy.deepcopy(old)
    if typ in WRITE:goal['rate']={'currency':m.meta(base),'value':1}
    assert same(goal,d,typ)
    assert r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1
    if typ in ('customerorder','demand','salesreturn'):assert b.D(d['payedSum'])==b.D(d['sum'])
    else:assert sum(b.D(o['linkedSum']) for o in d['operations'])==b.D(d['sum'])
  checked+=len(chains)
  save(db,'final_audit:'+str(batch),{'status':'verified','at':m.now(),'documents':final,'cases':len(chains)})
 assert ccstate(cc)==ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:apply:v1',{'status':'verified','at':m.now(),'verified_cases':checked,'documents':totals,'all_nominal_sums_preserved':True,'prices_quantities_order_links_preserved':True,'all_payments_fully_allocated':True,'currency_settings_unchanged':True,'global_counterparty_balance_checked':False,'excluded_preflight_cases':pf['conflicts'],'outside_ms_changes':False})
 print('Approved equal-amount chains normalized and completely read back; private results saved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:apply:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected normalization stopped; inspect private journal before retry.');sys.exit(1)
