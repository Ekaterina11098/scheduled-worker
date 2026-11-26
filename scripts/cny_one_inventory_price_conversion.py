"""One authorized inventory price-only correction with quantitative invariants."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_incoming_refs_apply as h
r=h.r;b=h.b;m=h.m;P='one_inventory_price_conversion:'
def save(db,k,v):b.put(db,P+k,v)
def qshape(d):
 return [{'id':p['id'],'assortment':m.href(p['assortment']),'quantity':r.number(p.get('quantity')),'calculatedQuantity':r.number(p.get('calculatedQuantity')),'correctionAmount':r.number(p.get('correctionAmount'))} for p in r.rows(d)]
def inv(old,new):
 h.related_inv(old,new);assert qshape(old)==qshape(new),'Inventory quantitative fields changed'
 for x,y in zip(r.rows(old),r.rows(new)):
  aa=r.psig(x);bb=r.psig(y);aa.pop('price');bb.pop('price');assert aa==bb
 for k in ('losses','enters'):
  assert sorted(m.href(x) for x in old.get(k,[]))==sorted(m.href(x) for x in new.get(k,[]))
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'authorization:v1')
 assert cfg['authorized'] and cfg['scope']=='one_inventory_price_conversion' and cfg['rub_per_cny']==12 and cfg['preserve_quantities'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Existing attempt requires readback reconciliation'
 i=cfg['id'];before=r.live(t,'inventory',[i])[i];inv(cfg['before'],before)
 assert r.signature(cfg['before'],'inventory')==r.signature(before,'inventory'),'Inventory changed after review'
 plan=b.plan(before,r.rows(before));assert b.D(plan['actual_minor'])==cfg['target_minor'] and b.D(plan['deviation_minor'])==0
 body={'positions':[]};goal=copy.deepcopy(before)
 for p,price in zip(r.rows(before),plan['price_minor']):
  pp={k:copy.deepcopy(p[k]) for k in ('id','quantity','pack','slot','things') if k in p}
  pp['assortment']=m.meta(p['assortment']);pp['price']=int(price);body['positions'].append(pp)
 goal['sum']=cfg['target_minor']
 goal['positions']['rows']=[{**p,'price':q['price']} for p,q in zip(r.rows(before),body['positions'])]
 refs={}
 for field in ('losses','enters'):
  for d in before.get(field,[]):refs.setdefault(d['meta']['type'],[]).append(m.href(d).split('/')[-1])
 linked={typ:r.live(t,typ,ids) for typ,ids in refs.items()}
 cc=b.fullrows(t,'entity/currency');assert next(c for c in cc if c.get('default'))['isoCode']=='CNY'
 wh0=h.warehouse(t)
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goal':goal,'body':body,'plan':plan,'linked_before':linked,'warehouse_before':wh0,'currencies':cc})
 fresh=r.live(t,'inventory',[i])[i];inv(before,fresh);assert r.signature(before,'inventory')==r.signature(fresh,'inventory')
 assert h.warehouse(t)==wh0,'Warehouse quantities changed before write'
 assert db.claim(b.ROOT+P+'intent:v1',{'at':m.now(),'id':i,'body':body}),'Existing intent: do not replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/inventory/'+i,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   value=json.loads(raw)
  save(db,'response:v1',{'at':m.now(),'received':True,'document':value})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   detail=json.loads(raw)
  except Exception:detail={'status':e.code}
  save(db,'response:v1',{'at':m.now(),'http_status':e.code,'detail':detail})
 except (TimeoutError,urllib.error.URLError):save(db,'response:v1',{'at':m.now(),'uncertain':True})
 for attempt in range(13):
  after=r.live(t,'inventory',[i])[i]
  if r.signature(after,'inventory')==r.signature(goal,'inventory'):break
  if attempt<12:time.sleep(15)
 save(db,'readback:v1',{'at':m.now(),'document':after})
 inv(before,after);assert r.signature(after,'inventory')==r.signature(goal,'inventory'),'Inventory target mismatch; no replay'
 for p in r.rows(after):
  assert b.D(p['correctionSum'])==b.R(b.D(p['price'])*b.D(p['correctionAmount'])),'Correction sum mismatch'
 linked_after={typ:r.live(t,typ,ids) for typ,ids in refs.items()}
 for typ,ds in linked_after.items():
  for j,d in ds.items():h.related_inv(linked[typ][j],d);assert r.signature(linked[typ][j],typ)==r.signature(d,typ),'Linked adjustment changed'
 wh1=h.warehouse(t);assert wh1==wh0,'Warehouse quantities changed'
 assert h.h.ccstate(cc)==h.h.ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:v1',{'status':'verified','at':m.now(),'before_minor':before['sum'],'after_minor':after['sum'],'before':before,'after':after,'linked_after':linked_after,'quantitative_fields_preserved':True,'position_order_preserved':True,'all_store_quantities_preserved':True,'linked_documents_unchanged':True,'warehouse_before':wh0,'warehouse_after':wh1,'currency_settings_unchanged':True,'outside_ms_changes':False})
 print('Selected inventory prices and total verified; quantitative fields and all warehouse stocks preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Inventory price test stopped; inspect private readback before any further write.');sys.exit(1)
