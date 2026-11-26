"""Apply one authorized full-return chain using its order unit price, preserving two units."""
import copy,gzip,json,os,sys,traceback,urllib.request,urllib.error
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='approved_two_units_chain:'
TYPES=('customerorder','demand','salesreturn','paymentin','paymentout')
def save(db,k,v):b.put(db,P+k,v)
def read(t,cfg):return {typ:r.live(t,typ,[cfg['documents'][typ]])[cfg['documents'][typ]] for typ in TYPES}
def same(x,y,typ):return r.signature(x,typ)==r.signature(y,typ)
def invariant(old,new):
 a.invariants(old,new)
 for op,np in zip(r.rows(old),r.rows(new)):
  x=r.psig(op);y=r.psig(np);x.pop('price');y.pop('price');assert x==y,'Position structure changed'
 assert [m.href(x) for x in old.get('operations',[])]==[m.href(x) for x in new.get('operations',[])],'Payment basis changed'
def ccstate(cc):return sorted([{k:c.get(k) for k in ('id','isoCode','rate','default','multiplicity','indirect','archived','name')} for c in cc],key=lambda c:c['id'])
def write(db,cfg,typ,body):
 path='entity/'+typ+'/'+cfg['documents'][typ]
 assert db.claim(b.ROOT+P+'intent:'+typ,{'status':'intended','at':m.now(),'path':path,'body':body}),'Existing intent; reconcile before replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+path,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=90) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,'response:'+typ,{'at':m.now(),'received':True,'document':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'http_status':e.code}
  save(db,'response:'+typ,{'at':m.now(),'received':True,'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,'response:'+typ,{'at':m.now(),'received':False,'uncertain':True})
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='one_approved_full_two_units_chain'
 assert cfg['target_minor']==23334 and cfg['unit_price_minor']==11667 and cfg['expected_quantity']==2
 assert not cfg['bulk_allowed'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt; reconcile before replay'
 before=read(t,cfg);cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['id']==cfg['base_currency_id'] and base['isoCode']=='CNY' and b.D(base['rate'])==1
 for typ,d in before.items():
  invariant(cfg['before'][typ],d)
  assert same(cfg['before'][typ],d,typ),'Changed since reviewed snapshot'
  if typ in ('customerorder','demand','salesreturn'):
   assert len(r.rows(d))==1 and b.D(r.rows(d)[0]['quantity'])==2
   assert b.D(r.rows(d)[0].get('discount'))==0 and b.D(r.rows(d)[0].get('vat'))==0
  else:assert b.D(d.get('vatSum'))==0
 assert len({m.href(r.rows(before[k])[0]['assortment']) for k in ('customerorder','demand','salesreturn')})==1
 assert b.D(before['customerorder']['sum'])==cfg['target_minor'] and b.D(r.rows(before['customerorder'])[0]['price'])==cfg['unit_price_minor']
 assert m.href(before['demand']['customerOrder'])==m.MS+'entity/customerorder/'+cfg['documents']['customerorder']
 assert m.href(before['salesreturn']['demand'])==m.MS+'entity/demand/'+cfg['documents']['demand']
 assert [m.href(x) for x in before['customerorder']['demands']]==[m.MS+'entity/demand/'+cfg['documents']['demand']]
 assert [m.href(x) for x in before['demand']['returns']]==[m.MS+'entity/salesreturn/'+cfg['documents']['salesreturn']]
 assert not before['customerorder'].get('payments')
 for pay,basis in (('paymentin','demand'),('paymentout','salesreturn')):
  assert len(before[pay]['operations'])==1 and m.href(before[pay]['operations'][0])==m.MS+'entity/'+basis+'/'+cfg['documents'][basis]
  assert [m.href(x) for x in before[basis]['payments']]==[m.MS+'entity/'+pay+'/'+cfg['documents'][pay]]
 goals=copy.deepcopy(before);bodies={}
 for typ,d in before.items():
  body={};goal=goals[typ]
  if r.currency(d)!=m.href(base) or b.D(d['rate'].get('value',1))!=1:body['rate']={'currency':m.meta(base),'value':1}
  goal['rate']={'currency':m.meta(base),'value':1};goal['sum']=cfg['target_minor']
  if typ in ('customerorder','demand','salesreturn'):
   old=r.rows(d)[0];q={k:copy.deepcopy(old[k]) for k in r.FIELDS if k in old}
   q['assortment']=m.meta(old['assortment']);q['price']=cfg['unit_price_minor'];body['positions']=[q]
   goal['positions']['rows'][0]['price']=cfg['unit_price_minor']
  else:
   body['sum']=cfg['target_minor'];body['operations']=[{**m.meta(d['operations'][0]),'linkedSum':cfg['target_minor']}]
   goal['operations']=body['operations']
  bodies[typ]=body
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goals':goals,'bodies':bodies,'currencies':cc})
 expected=copy.deepcopy(before)
 for typ,body in bodies.items():
  fresh=read(t,cfg)
  for k,d in fresh.items():
   invariant(before[k],d);assert same(expected[k],d,k),'Concurrent edit'
  if not same(before[typ],goals[typ],typ):write(db,cfg,typ,body)
  expected[typ]=goals[typ];after=read(t,cfg)
  save(db,'readback:'+typ,{'at':m.now(),'documents':after})
  for k,d in after.items():
   invariant(before[k],d);assert same(expected[k],d,k),'Target not saved; stop without replay'
  save(db,'verified:'+typ,{'status':'verified','at':m.now()})
 final=read(t,cfg)
 for typ,d in final.items():
  invariant(before[typ],d);assert same(goals[typ],d,typ)
  assert b.D(d['sum'])==cfg['target_minor'] and r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1
  if typ in ('customerorder','demand','salesreturn'):assert b.D(d['payedSum'])==cfg['target_minor']
  else:assert b.D(d['operations'][0]['linkedSum'])==cfg['target_minor']
 assert ccstate(cc)==ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:v1',{'status':'verified','at':m.now(),'documents':final,'target_minor':cfg['target_minor'],'unit_price_minor':cfg['unit_price_minor'],'quantity':2,'positions_quantity_order_links_preserved':True,'all_payments_fully_allocated':True,'currency_settings_unchanged':True,'global_counterparty_balance_checked':False,'bulk_enabled':False})
 print('Selected full-return chain aligned to approved order price and completely verified.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected two-unit chain stopped; inspect private journal before retry.');sys.exit(1)
