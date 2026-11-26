"""Complete a single authorized chain after reconciling automatic currency price conversion."""
import copy,gzip,json,os,sys,traceback,urllib.request,urllib.error
import cny_one_partial_payment_base_test as z
a=z.a;r=z.r;b=z.b;m=z.m
P='one_partial_payment_base_cny_complete:'
def save(db,k,v):b.put(db,P+k,v)
def put_once(db,cfg,typ,body,label):
 assert typ in ('customerorder','demand','paymentin','paymentout')
 assert set(body)<=set(('rate','positions','sum','operations'))
 path='entity/'+typ+'/'+cfg['documents'][typ]
 assert db.claim(b.ROOT+P+'intent:'+label,{'status':'intended','at':m.now(),'path':path,'body':body}),'Existing intent: reconcile, no replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+path,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=90) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,'response:'+label,{'received':True,'at':m.now(),'document':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':e.code}
  save(db,'response:'+label,{'received':True,'at':m.now(),'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,'response:'+label,{'received':False,'uncertain':True,'at':m.now()})
def positions(d,target):
 out=[]
 for old in r.rows(d):
  p={k:copy.deepcopy(old[k]) for k in r.FIELDS if k in old};p['assortment']=m.meta(old['assortment']);p['price']=target;out.append(p)
 return out
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+z.P+'config:v1');snap=db.get(b.ROOT+z.P+'snapshot:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_chain_base_cny_preserve_nominal_and_full_refund'
 assert cfg['expected_sum_minor']==14167 and not cfg['bulk_allowed'] and not cfg['outside_ms_changes']
 assert snap and not db.get(b.ROOT+P+'snapshot:v1')
 before=snap['before'];goals=snap['goals'];target=cfg['expected_sum_minor']
 expected=copy.deepcopy(before)
 expected['customerorder']=copy.deepcopy(goals['customerorder'])
 expected['customerorder']['sum']=target*12
 expected['customerorder']['positions']['rows'][0]['price']=target*12
 fresh=z.read(t,cfg)
 for typ,d in fresh.items():
  a.invariants(before[typ],d)
  assert z.same(expected[typ],d,typ),'Live state differs from known stopped readback'
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before_completion':fresh,'original':before,'goals':goals})
 expected=fresh
 for typ in ('customerorder','demand','paymentin','paymentout'):
  current=z.read(t,cfg)
  for k,d in current.items():
   a.invariants(before[k],d)
   assert z.same(expected[k],d,k),'Concurrent edit before write'
  body={}
  if r.currency(current[typ])!=r.currency(goals[typ]) or b.D(current[typ]['rate'].get('value',1))!=1:body['rate']=goals[typ]['rate']
  if typ in ('customerorder','demand'):body['positions']=positions(before[typ],target)
  else:body.update(sum=target,operations=goals[typ]['operations'])
  put_once(db,cfg,typ,body,typ)
  after=z.read(t,cfg)
  save(db,'readback:'+typ,{'at':m.now(),'documents':after})
  for k,d in after.items():
   a.invariants(before[k],d)
   if k!=typ:assert z.same(expected[k],d,k),'Other document monetary state changed'
  if not z.same(goals[typ],after[typ],typ):
   d=after[typ]
   assert r.currency(d)==r.currency(goals[typ]) and b.D(d['rate'].get('value',1))==1,'Currency target not saved'
   allowed=copy.deepcopy(goals[typ])
   if typ in ('customerorder','demand'):
    allowed['sum']=target*12;allowed['positions']['rows'][0]['price']=target*12
    assert z.same(allowed,d,typ),'Unexpected automatic conversion'
    correction={'positions':positions(before[typ],target)}
   else:
    assert b.D(d['sum']) in (target,target*12)
    assert len(d['operations'])==1 and m.href(d['operations'][0])==m.href(goals[typ]['operations'][0])
    assert b.D(d['operations'][0]['linkedSum']) in (target,target*12,b.D(before[typ]['operations'][0]['linkedSum']))
    assert b.D(d.get('vatSum'))==b.D(goals[typ].get('vatSum'))
    correction={'sum':target,'operations':goals[typ]['operations']}
   save(db,'automatic_conversion:'+typ,{'at':m.now(),'observed':d,'correction':correction})
   confirm=z.read(t,cfg)
   for k,doc in confirm.items():assert z.same(after[k],doc,k),'Changed before correction'
   put_once(db,cfg,typ,correction,typ+':preserve_nominal')
   after=z.read(t,cfg);save(db,'correction_readback:'+typ,{'at':m.now(),'documents':after})
  expected[typ]=goals[typ]
  for k,d in after.items():
   a.invariants(before[k],d)
   assert z.same(expected[k],d,k),'Target mismatch after correction'
  save(db,'verified:'+typ,{'status':'verified','at':m.now()})
 final=z.read(t,cfg);cc=b.fullrows(t,'entity/currency')
 assert z.currency_state(cc)==z.currency_state(snap['currencies']),'Global currency settings changed'
 for typ,d in final.items():
  z.invariant(before[typ],d)
  assert z.same(goals[typ],d,typ)
  assert r.currency(d)==m.MS+'entity/currency/'+cfg['base_currency_id'] and b.D(d['rate'].get('value',1))==1
 for typ in ('customerorder','demand','salesreturn'):assert b.D(final[typ]['payedSum'])==target
 for pay,basis in (('paymentin','demand'),('paymentout','salesreturn')):
  assert b.D(final[pay]['operations'][0]['linkedSum'])==target
  assert len(final[basis]['payments'])==1 and b.D(final[basis]['payments'][0]['linkedSum'])==target
 summary=[{'type':typ,'id':d['id'],'sum_minor':d['sum'],'payedSum':d.get('payedSum'),'rate':d['rate'].get('value',1),'allocated_minor':sum(o['linkedSum'] for o in d.get('operations',[]))} for typ,d in final.items()]
 save(db,'result:v1',{'status':'verified','at':m.now(),'documents':final,'summary':summary,'nominal_sum_preserved':True,'prices_quantities_order_links_preserved':True,'global_currency_settings_unchanged':True,'all_payment_allocations_full':True,'chain_payment_net_minor':final['paymentin']['sum']-final['paymentout']['sum'],'global_counterparty_balance_checked':False,'bulk_enabled':False})
 print('One chain verified with original nominal prices and complete allocation; private result saved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('One chain completion stopped; inspect private journal before retry.');sys.exit(1)
