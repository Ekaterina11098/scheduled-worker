"""One explicitly authorized chain: normalize CNY reference, preserve prices, allocate refund."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m
P='one_partial_payment_base_cny_test:'
TYPES=('customerorder','demand','salesreturn','paymentin','paymentout')
def save(db,k,v):b.put(db,P+k,v)
def read(t,cfg):return {typ:r.live(t,typ,[cfg['documents'][typ]])[cfg['documents'][typ]] for typ in TYPES}
def invariant(old,new):
 a.invariants(old,new)
 assert [r.psig(p) for p in r.rows(old)]==[r.psig(p) for p in r.rows(new)],'Position data or prices changed'
 assert b.D(old['sum'])==b.D(new['sum']),'Nominal amount changed'
 assert [m.href(x) for x in old.get('operations',[])]==[m.href(x) for x in new.get('operations',[])],'Payment basis changed'
def same(a0,a1,typ):return r.signature(a0,typ)==r.signature(a1,typ)
def currency_state(cc):
 return sorted([{k:c.get(k) for k in ('id','isoCode','rate','default','multiplicity','indirect','archived','name')} for c in cc],key=lambda x:x['id'])
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_chain_base_cny_preserve_nominal_and_full_refund'
 assert cfg['expected_sum_minor']==14167 and not cfg['bulk_allowed'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt: reconcile before replay'
 inspection=db.get(b.ROOT+'one_partial_payment_rate:inspection:v1');assert inspection and inspection['status']=='complete'
 before=read(t,cfg);cc=b.fullrows(t,'entity/currency')
 base=next(c for c in cc if c.get('default'))
 assert base['isoCode']=='CNY' and b.D(base['rate'])==1 and base['id']==cfg['base_currency_id']
 currencies={m.href(c):c for c in cc}
 target=cfg['expected_sum_minor']
 for typ,d in before.items():
  invariant(inspection['documents'][typ],d)
  assert same(inspection['documents'][typ],d,typ),'Changed since inspection'
  assert b.D(d['sum'])==target and currencies[r.currency(d)]['isoCode']=='CNY'
  if typ in ('customerorder','demand','salesreturn'):
   assert len(r.rows(d))==1 and b.D(r.rows(d)[0]['quantity'])==1
 assert m.href(before['demand']['customerOrder'])==m.MS+'entity/customerorder/'+cfg['documents']['customerorder']
 assert m.href(before['salesreturn']['demand'])==m.MS+'entity/demand/'+cfg['documents']['demand']
 for pay,basis in (('paymentin','demand'),('paymentout','salesreturn')):
  assert len(before[pay]['operations'])==1 and m.href(before[pay]['operations'][0])==m.MS+'entity/'+basis+'/'+cfg['documents'][basis]
 assert b.D(before['paymentout']['operations'][0]['linkedSum'])==9834
 goals=copy.deepcopy(before);bodies={}
 for typ in ('customerorder','demand','paymentin','paymentout'):
  body={'rate':{'currency':m.meta(base),'value':1}}
  goals[typ]['rate']=body['rate']
  if typ in ('paymentin','paymentout'):
   body['sum']=target
   body['operations']=[{**m.meta(before[typ]['operations'][0]),'linkedSum':target}]
   goals[typ]['operations']=body['operations']
  bodies[typ]=body
 assert r.currency(before['salesreturn'])==m.href(base) and b.D(before['salesreturn']['rate'].get('value',1))==1
 save(db,'snapshot:v1',{'status':'prepared','at':m.now(),'before':before,'currencies':cc,'goals':goals,'bodies':bodies})
 expected=copy.deepcopy(before)
 for typ,body in bodies.items():
  fresh=read(t,cfg)
  for k,d in fresh.items():
   invariant(before[k],d)
   assert same(expected[k],d,k),'Concurrent monetary edit; stopped'
  path='entity/'+typ+'/'+cfg['documents'][typ]
  assert set(body)<=set(('rate','sum','operations'))
  key=b.ROOT+P+'intent:'+typ
  assert db.claim(key,{'status':'intended','at':m.now(),'path':path,'body':body}),'Existing intent; no blind retry'
  headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
  req=urllib.request.Request(m.MS+path,data=json.dumps(body).encode(),headers=headers,method='PUT')
  try:
   with urllib.request.urlopen(req,timeout=90) as response:
    raw=response.read()
    if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
    result=json.loads(raw)
   save(db,'response:'+typ,{'received':True,'at':m.now(),'document':result})
  except urllib.error.HTTPError as e:
   raw=e.read()
   try:
    if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
    detail=json.loads(raw)
   except Exception:detail={'http_status':e.code}
   save(db,'response:'+typ,{'received':True,'http_status':e.code,'detail':detail,'at':m.now()})
  except (TimeoutError,urllib.error.URLError):
   save(db,'response:'+typ,{'received':False,'uncertain':True,'at':m.now()})
  expected[typ]=goals[typ]
  after=read(t,cfg)
  save(db,'readback:'+typ,{'at':m.now(),'documents':after})
  for k,d in after.items():
   invariant(before[k],d)
   assert same(expected[k],d,k),'Readback target mismatch; stop and reconcile'
  save(db,'verified:'+typ,{'status':'verified','at':m.now()})
 final=read(t,cfg);cc_after=b.fullrows(t,'entity/currency')
 assert currency_state(cc)==currency_state(cc_after),'Currency settings changed'
 for typ,d in final.items():
  invariant(before[typ],d)
  assert same(goals[typ],d,typ)
  assert r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1
 for typ in ('customerorder','demand','salesreturn'):
  assert b.D(final[typ]['payedSum'])==target,'Paid amount mismatch'
 for pay,basis in (('paymentin','demand'),('paymentout','salesreturn')):
  assert b.D(final[pay]['operations'][0]['linkedSum'])==target
  assert len(final[basis]['payments'])==1 and b.D(final[basis]['payments'][0]['linkedSum'])==target
 summary=[{'type':typ,'id':d['id'],'name':d['name'],'sum_minor':d['sum'],'payedSum':d.get('payedSum'),'currency_id':base['id'],'rate':d['rate'].get('value',1),'allocated_minor':sum(x.get('linkedSum',0) for x in d.get('operations',[]))} for typ,d in final.items()]
 save(db,'result:v1',{'status':'verified','at':m.now(),'documents':final,'summary':summary,'currencies_unchanged':True,'positions_prices_quantities_links_preserved':True,'nominal_sum_preserved':True,'payment_allocations_full':True,'chain_payment_net_minor':final['paymentin']['sum']-final['paymentout']['sum'],'global_counterparty_balance_checked':False,'bulk_enabled':False})
 print('Single CNY chain normalization and full refund allocation verified; private result saved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Single chain test stopped; inspect private journal before any retry.');sys.exit(1)
