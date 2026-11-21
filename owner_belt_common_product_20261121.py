"""Create one owner-requested common MS product; zero quantity, no movements."""
import json,time,uuid
import tg_agent_new as g
from stock_deploy_support import runtime_db,seal,error
from stock_operation_store import Store,Stopped,canonical,digest
from stock_execution_fence import cloud_writer
ROOT='technical:owner-belt-common-product:2026-11-21'
ARTICLE='5belts-chocolate'
CODES=['2044635464927','2044635464934','2044635464941','2044635464958']
SYNC=str(uuid.uuid5(uuid.NAMESPACE_URL,'veschi:wb:ip:454004208:common-stock:v1'))
with runtime_db() as lock:
 with cloud_writer(lock):
  with runtime_db() as db:
   s=Store(db,postgres=True);row=s.sql('SELECT snapshot FROM stock_runs WHERE id=?',(ROOT,)).fetchone();db.commit()
   data=json.loads(row[0]) if row else {'status':'prepared','started':time.time(),'approval':{'instruction':'Настрой 5belts-chocolate как один артикул с общим остатком и резервами','article':ARTICLE,'cabinet':1,'nmID':454004208,'initial_quantity':0,'syncId':SYNC}}
   def save():
    with s.transaction():s.sql('INSERT INTO stock_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot',(ROOT,canonical(data),canonical(data['approval']),digest(data['approval']),'cloud-owner-metadata',data['started']))
   g.check_run_budget=lambda:None
   try:
    goods=g.ms_rows(g.MS_API+'/entity/assortment',filter='archived=false;archived=true')
    existing=[p for p in goods if g.norm(p.get('article'))==ARTICLE or p.get('syncId')==SYNC]
    if len(existing)>1:raise Stopped('Duplicate common product; do not merge stock')
    if existing:
     product=existing[0]
     if g.norm(product.get('article'))!=ARTICLE:raise Stopped('Common product identity mismatch')
    else:
     if data.get('creation_claimed'):raise Stopped('Earlier creation outcome unknown; read only, never blind recreate')
     conflicts=[p['id'] for p in goods if p.get('id') and set(CODES)&{str(v) for b in p.get('barcodes',[]) for v in b.values()}]
     if conflicts:raise Stopped('WB barcode already belongs to another MS product')
     payload={'name':'Ремень кожа тиснение овал шоколадный','article':ARTICLE,'code':'WB-IP-454004208','externalCode':'wb-ip-454004208-common-v1','syncId':SYNC,'barcodes':[{'ean13':c} for c in CODES],'description':'Единый артикул 5belts-chocolate. Общий остаток и резерв для технических размеров карточки WB ИП 454004208. Приходы учитываются на этой позиции.'}
     data.update(creation_claimed=True,payload=payload,status='creating');save()
     product=g.api('POST',g.MS_API+'/entity/product',g.MS_TOKEN,wb=False,json=payload)
     data['create_response']=product;save()
    actual=g.api('GET',g.MS_API+'/entity/product/'+product['id'],g.MS_TOKEN,wb=False,retry_read_network=True)
    actual_codes={str(v) for b in actual.get('barcodes',[]) for v in b.values()}
    if g.norm(actual.get('article'))!=ARTICLE or not set(CODES).issubset(actual_codes) or actual.get('archived') is True:raise Stopped('Created common product readback differs')
    data.update(status='complete',product=actual,completed=time.time(),stock_movements_created=0);save()
   except Exception as exc:data.update(status='stopped',error=str(exc),error_type=type(exc).__name__);save();seal('belt-common-product-error',error(exc));raise
seal('belt-common-product',data)
print(json.dumps({'status':'complete','stock_movements_created':0}))
