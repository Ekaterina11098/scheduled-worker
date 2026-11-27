"""Normalize one invoice source chain references, preserving prices and all stock quantities."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_incoming_refs_apply as h
r=h.r;b=h.b;m=h.m;P='invoice_order_demand_align:'
def save(db,k,v):b.put(db,P+k,v)
def write(db,typ,i,body):
 assert typ in ('customerorder','demand') and set(body)=={'rate','positions'}
 assert db.claim(b.ROOT+P+'intent:'+typ,{'at':m.now(),'type':typ,'id':i,'body':body}),'Existing intent: reconcile before replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/'+typ+'/'+i,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   data=json.loads(raw)
  save(db,'response:'+typ,{'at':m.now(),'received':True,'document':data})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'status':e.code}
  save(db,'response:'+typ,{'at':m.now(),'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,'response:'+typ,{'at':m.now(),'uncertain':True})
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'authorization:v1')
 assert cfg['authorized'] and cfg['scope']=='one_invoice_source_chain_currency_reference_alignment'
 assert cfg['preserve_nominal_order_shipment_prices'] and cfg['preserve_quantities'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt requires reconciliation'
 pf=db.get(b.ROOT+P+'preflight:v1')
 assert pf['status']=='complete' and pf['same_order_shipment_items_quantities'] and pf['same_nominal_order_shipment_sum']
 before={typ:r.live(t,typ,[d['id']])[d['id']] for typ,d in pf['documents'].items()}
 for typ,d in before.items():
  h.related_inv(pf['documents'][typ],d);assert r.signature(pf['documents'][typ],typ)==r.signature(d,typ)
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'))
 assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 target=b.D(before['customerorder']['sum']);assert target==b.D(before['demand']['sum'])>0
 assert b.D(before['factureout']['sum'])==target*12
 assert r.currency(before['factureout'])==m.href(base) and b.D(before['factureout']['rate'].get('value',1))==1
 goals=copy.deepcopy(before);bodies={}
 for typ in ('customerorder','demand'):
  d=before[typ];assert b.D(d['rate'].get('value',1))==12
  assert next(c['isoCode'] for c in cc if m.href(c)==r.currency(d))=='CNY'
  body={'rate':{'currency':m.meta(base),'value':1},'positions':[]}
  for p in r.rows(d):
   q={k:copy.deepcopy(p[k]) for k in r.FIELDS if k in p};q['assortment']=m.meta(p['assortment']);q['price']=p['price'];body['positions'].append(q)
  bodies[typ]=body;goals[typ]['rate']=body['rate']
 goals['factureout']['sum']=int(target)
 linked={}
 for typ,ds in pf['related'].items():linked[typ]=r.live(t,typ,list(ds))
 for typ,ds in linked.items():
  for i,d in ds.items():h.related_inv(pf['related'][typ][i],d);assert r.signature(pf['related'][typ][i],typ)==r.signature(d,typ)
 wh0=h.warehouse(t);assert wh0==pf['warehouse_quantities'],'Warehouse quantities changed since preflight'
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goals':goals,'bodies':bodies,'related_before':linked,'warehouse_before':wh0,'currencies':cc,'target_minor':int(target)})
 expected=copy.deepcopy(before)
 for typ in ('customerorder','demand'):
  current={k:r.live(t,k,[d['id']])[d['id']] for k,d in before.items()}
  for k,d in current.items():
   h.related_inv(expected[k],d);assert r.signature(expected[k],k)==r.signature(d,k),'Concurrent chain edit'
  assert h.warehouse(t)==wh0
  write(db,typ,before[typ]['id'],bodies[typ])
  for attempt in range(13):
   d=r.live(t,typ,[before[typ]['id']])[before[typ]['id']]
   if r.signature(d,typ)==r.signature(goals[typ],typ):break
   if attempt<12:time.sleep(15)
  save(db,'readback:'+typ,{'at':m.now(),'document':d})
  h.h.inv(before[typ],d);assert r.signature(d,typ)==r.signature(goals[typ],typ),'Source currency mismatch; no replay'
  expected[typ]=d
  if typ=='demand':expected['factureout']=goals['factureout']
 final=None
 for attempt in range(13):
  final={k:r.live(t,k,[d['id']])[d['id']] for k,d in before.items()}
  if all(r.signature(final[k],k)==r.signature(goals[k],k) for k in final):break
  if attempt<12:time.sleep(15)
 save(db,'final_readback:v1',{'at':m.now(),'documents':final})
 for typ,d in final.items():
  h.related_inv(before[typ],d);assert r.signature(d,typ)==r.signature(goals[typ],typ),'Final invoice chain mismatch'
  if typ!='factureout':h.h.inv(before[typ],d)
 for typ,ds in linked.items():
  for i,d in r.live(t,typ,list(ds)).items():
   h.related_inv(ds[i],d);assert r.signature(ds[i],typ)==r.signature(d,typ),'Related payment changed'
 wh1=h.warehouse(t);assert wh1==wh0
 assert h.h.ccstate(cc)==h.h.ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:v1',{'status':'verified','at':m.now(),'documents':final,'target_minor':int(target),'all_three_sums_equal':True,'all_order_shipment_prices_quantities_order_preserved':True,'all_store_quantities_preserved':True,'related_payments_preserved':True,'warehouse_before':wh0,'warehouse_after':wh1,'currency_settings_unchanged':True,'outside_ms_changes':False})
 print('Selected invoice and source chain totals verified equal; prices and warehouse quantities preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:apply:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected invoice chain correction stopped; reconcile private readback before further writes.');sys.exit(1)
