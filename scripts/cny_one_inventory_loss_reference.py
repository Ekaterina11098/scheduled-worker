"""One authorized loss currency reference correction; preserve nominal amounts and quantities."""
import copy,gzip,json,os,sys,time,traceback,urllib.request,urllib.error
import cny_incoming_refs_apply as h
import cny_one_inventory_price_conversion as inv
r=h.r;b=h.b;m=h.m;P='one_inventory_loss_reference:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'authorization:v1')
 assert cfg['authorized'] and cfg['scope']=='one_selected_loss_currency_reference' and cfg['preserve_quantities'] and not cfg['outside_ms_changes']
 assert not db.get(b.ROOT+P+'snapshot:v1'),'Prior attempt: reconcile before replay'
 i=cfg['loss_id'];ii=cfg['inventory_id']
 before=r.live(t,'loss',[i])[i];inventory=r.live(t,'inventory',[ii])[ii]
 h.h.inv(cfg['before'],before);assert r.signature(cfg['before'],'loss')==r.signature(before,'loss')
 inv.inv(cfg['inventory_before'],inventory);assert r.signature(cfg['inventory_before'],'inventory')==r.signature(inventory,'inventory')
 assert b.D(before['sum'])==cfg['expected_sum_minor'] and b.D(before['rate'].get('value',1))==12
 assert m.href(before.get('inventory',{}))==m.MS+'entity/inventory/'+ii,'Inventory link mismatch'
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'));assert base['isoCode']=='CNY' and b.D(base['rate'])==1
 body={'rate':{'currency':m.meta(base),'value':1},'positions':[]}
 for p in r.rows(before):
  pp={k:copy.deepcopy(p[k]) for k in r.FIELDS if k in p};pp['assortment']=m.meta(p['assortment']);pp['price']=p['price'];body['positions'].append(pp)
 goal=copy.deepcopy(before);goal['rate']=body['rate']
 wh0=h.warehouse(t)
 save(db,'snapshot:v1',{'at':m.now(),'before':before,'goal':goal,'body':body,'inventory_before':inventory,'warehouse_before':wh0,'currencies':cc})
 fresh=r.live(t,'loss',[i])[i];h.h.inv(before,fresh);assert r.signature(before,'loss')==r.signature(fresh,'loss')
 assert h.warehouse(t)==wh0,'Warehouse quantity changed before write'
 assert db.claim(b.ROOT+P+'intent:v1',{'at':m.now(),'id':i,'body':body}),'Existing write intent: no replay'
 headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Content-Type':'application/json','Accept':'application/json;charset=utf-8','Accept-Encoding':'gzip'}
 req=urllib.request.Request(m.MS+'entity/loss/'+i,data=json.dumps(body).encode(),headers=headers,method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=120) as resp:
   raw=resp.read()
   if resp.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   result=json.loads(raw)
  save(db,'response:v1',{'at':m.now(),'received':True,'document':result})
 except urllib.error.HTTPError as e:
  raw=e.read()
  try:
   if e.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
   error=json.loads(raw)
  except Exception:error={'status':e.code}
  save(db,'response:v1',{'at':m.now(),'http_status':e.code,'detail':error})
 except (TimeoutError,urllib.error.URLError):save(db,'response:v1',{'at':m.now(),'uncertain':True})
 for attempt in range(13):
  after=r.live(t,'loss',[i])[i]
  if r.signature(after,'loss')==r.signature(goal,'loss'):break
  if attempt<12:time.sleep(15)
 save(db,'readback:v1',{'at':m.now(),'document':after})
 h.h.inv(before,after);assert r.signature(after,'loss')==r.signature(goal,'loss'),'Loss target mismatch; no replay'
 assert m.href(after.get('inventory',{}))==m.href(before.get('inventory',{}))
 ia=r.live(t,'inventory',[ii])[ii];inv.inv(inventory,ia);assert r.signature(inventory,'inventory')==r.signature(ia,'inventory')
 assert r.rows(inventory)==r.rows(ia),'Inventory position fields changed'
 wh1=h.warehouse(t);assert wh1==wh0,'Warehouse quantities changed'
 assert h.h.ccstate(cc)==h.h.ccstate(b.fullrows(t,'entity/currency'))
 save(db,'result:v1',{'status':'verified','at':m.now(),'before':before,'after':after,'inventory_after':ia,'sum_minor':after['sum'],'nominal_prices_positions_preserved':True,'inventory_unchanged':True,'all_store_quantities_preserved':True,'warehouse_before':wh0,'warehouse_after':wh1,'currency_settings_unchanged':True,'outside_ms_changes':False})
 print('Selected loss currency reference verified; nominal prices and all warehouse quantities preserved.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Selected loss correction stopped; reconcile private readback before any further write.');sys.exit(1)
