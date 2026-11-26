"""Authorized conversion of five supplier return prices with immutable stock quantities."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_incoming_refs_apply as h
r=h.r;b=h.b;m=h.m;P='thirteen_buyer_return_conversion:'
def save(db,k,v):b.put(db,P+k,v)
def invariant(old,new):
 h.related_inv(old,new)
 for k in ('demand','customerOrder'):
  assert m.href(old.get(k,{}))==m.href(new.get(k,{})),'Source link changed'
 assert r.currency(old)==r.currency(new) and b.D(old['rate'].get('value',1))==b.D(new['rate'].get('value',1)),'Return currency changed unexpectedly'
 for x,y in zip(r.rows(old),r.rows(new)):
  aa=r.psig(x);bb=r.psig(y);aa.pop('price');bb.pop('price');assert aa==bb,'Non-price position field changed'
def write(db,i,body):
 assert set(body)=={'positions'}
 assert db.claim(b.ROOT+P+'intent:'+i,{'at':m.now(),'id':i,'body':body}),'Existing write intent: reconcile before any replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/salesreturn/'+i,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   result=json.loads(raw)
  save(db,'response:'+i,{'at':m.now(),'received':True,'document':result})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   error=json.loads(raw)
  except Exception:error={'status':e.code}
  save(db,'response:'+i,{'at':m.now(),'http_status':e.code,'detail':error})
 except (TimeoutError,urllib.error.URLError):save(db,'response:'+i,{'at':m.now(),'uncertain':True})
def read_related(t,refs):
 out={}
 for typ,ids in refs.items():
  out[typ]={}
  ss=sorted(ids)
  for o in range(0,len(ss),50):out[typ].update(r.live(t,typ,ss[o:o+50]))
 return out
def add(refs,obj):
 if not obj:return
 typ=obj['meta']['type'];assert typ in ('demand','customerorder','paymentin','paymentout','cashin','cashout')
 refs.setdefault(typ,set()).add(m.href(obj).split('/')[-1])
def check_related(t,related):
 for typ,old in related.items():
  now=r.live(t,typ,list(old))
  for i,d in now.items():
   h.related_inv(old[i],d)
   assert r.signature(old[i],typ)==r.signature(d,typ),'Related document monetary values changed'
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'authorization:v1')
 assert cfg['authorized'] and cfg['scope']=='thirteen_selected_buyer_returns_price_conversion'
 assert cfg['rub_per_cny']==12 and cfg['preserve_quantities'] and cfg['preserve_position_order'] and cfg['nearest_reachable_allowed'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Prior execution must be reconciled before resuming'
 targets=sorted(cfg['targets'],key=lambda x:(x['moment'],x['number']));assert len(targets)==13
 ids=[d['id'] for d in targets]
 audited=db.get(b.ROOT+'all_document_currency_audit_post_incoming:suspect_returns_detail:v1')['returns']
 before=r.live(t,'salesreturn',ids)
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'));assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 goals={};bodies={};plans={};refs={}
 for x in targets:
  i=x['id'];d=before[i];old=audited[i]
  assert d['applicable'] and not d.get('payments'),'Unexpected payment association or unposted return'
  assert r.currency(d)==m.href(base) and b.D(d['rate'].get('value',1))==1
  invariant(old,d);assert r.signature(old,'salesreturn')==r.signature(d,'salesreturn'),'Return changed after audit'
  assert b.D(d['sum'])==b.D(x['current_minor'])
  body,sig,plan=r.prepare(d,'salesreturn',base)
  assert b.D(plan['target_minor'])==b.D(x['target_minor']),'Unexpected target amount'
  assert all(b.D(p['price'])==int(p['price']) for p in body['positions'])
  g=copy.deepcopy(d);g['sum']=int(plan['actual_minor']);g['positions']['rows']=[{**p,'price':q['price']} for p,q in zip(r.rows(d),body['positions'])]
  bodies[i]={'positions':body['positions']};goals[i]=g;plans[i]=plan
  add(refs,d.get('demand'))
 related=read_related(t,refs)
 for ds in list(related.values()):
  for d in ds.values():
   add(refs,d.get('customerOrder'))
   for pp in d.get('payments',[]):add(refs,pp)
 related=read_related(t,refs)
 for ds in list(related.values()):
  for d in ds.values():
   for pp in d.get('payments',[]):add(refs,pp)
 related=read_related(t,refs);wh0=h.warehouse(t)
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goals':goals,'bodies':bodies,'plans':plans,'related_before':related,'warehouse_before':wh0,'currencies':cc})
 expected=copy.deepcopy(before);verified=[]
 for x in targets:
  i=x['id'];fresh=r.live(t,'salesreturn',ids)
  for j,d in fresh.items():
   invariant(expected[j],d);assert r.signature(expected[j],'salesreturn')==r.signature(d,'salesreturn'),'Concurrent return edit'
  check_related(t,related);assert h.warehouse(t)==wh0,'Warehouse quantities changed before write'
  write(db,i,bodies[i])
  for attempt in range(13):
   d=r.live(t,'salesreturn',[i])[i]
   if r.signature(d,'salesreturn')==r.signature(goals[i],'salesreturn'):break
   if attempt<12:time.sleep(15)
  save(db,'readback:'+i,{'at':m.now(),'document':d})
  invariant(before[i],d);assert r.signature(d,'salesreturn')==r.signature(goals[i],'salesreturn'),'Target did not persist; no write replay'
  check_related(t,related);assert h.warehouse(t)==wh0,'Warehouse quantity mismatch after write'
  expected[i]=d;verified.append({'id':i,'name':d['name'],'moment':d['moment'],'sum_minor':d['sum'],'positions':len(r.rows(d)),'target_minor':plans[i]['target_minor'],'deviation_minor':plans[i]['deviation_minor']})
  save(db,'progress:v1',{'at':m.now(),'status':'running','verified':verified,'warehouse_quantities_preserved':True,'related_documents_preserved':True})
 final=r.live(t,'salesreturn',ids)
 for i,d in final.items():invariant(before[i],d);assert r.signature(expected[i],'salesreturn')==r.signature(d,'salesreturn')
 check_related(t,related);wh1=h.warehouse(t);assert wh1==wh0
 assert h.h.ccstate(cc)==h.h.ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:v1',{'status':'verified','at':m.now(),'verified':verified,'documents':final,'plans':plans,'warehouse_before':wh0,'warehouse_after':wh1,'all_store_quantities_preserved':True,'position_quantities_order_preserved':True,'linked_orders_shipments_payments_unchanged':True,'currency_settings_unchanged':True,'outside_ms_changes':False})
 print('Selected buyer return conversion verified; all warehouse quantities and related documents preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Buyer return correction stopped; inspect private readback before any further write.');sys.exit(1)
