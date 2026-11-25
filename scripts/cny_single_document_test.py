"""Single explicitly selected purchase-order currency test. Business inputs stay private."""
import argparse,copy,gzip,json,os,sys,urllib.request,urllib.error
from decimal import Decimal
import cny_migration_backup_20261125 as b
m=b.m;ROOT=b.ROOT+'single_test:'
def save(db,key,value):b.put(db,'single_test:'+key,value)
def getdoc(t,path):
 d=t.request(m.MS,path,params={'expand':'rate.currency'})
 if isinstance(d.get('positions'),dict):
  d['positions']={**d['positions'],'rows':b.fullrows(t,path+'/positions')}
 return d
def stable(d):
 return {k:v for k,v in d.items() if k not in ('meta','updated','printed','published','files')}
def money(d):
 return {'sum':d.get('sum'),'rate':d.get('rate'),'operations':d.get('operations'),'positions':[(p['id'],p.get('quantity'),p.get('price')) for p in d.get('positions',{}).get('rows',[])]}
def readlinks(t,d):
 out={}
 for key in ('payments','supplies'):
  for item in d.get(key,[]):
   url=m.href(item);assert url.startswith(m.MS+'entity/')
   path=url[len(m.MS):].split('?')[0]
   assert path.split('/')[1] in ('paymentout','cashout','supply')
   out[path]=getdoc(t,path)
 return out
class NarrowWriter(b.ReadOnly):
 def __init__(self,db,target):super().__init__();self.db=db;self.target=target
 def write_once(self,path,method,body,label):
  assert (path=='entity/currency' and method=='POST') or (path==self.target and method=='PUT')
  key=ROOT+label
  if not self.db.claim(key,{'status':'intended','at':m.now(),'method':method,'path':path,'body':body}):
   raise m.Stop('Write intent already exists: reconcile before any retry')
  headers={'Accept':'application/json;charset=utf-8','Content-Type':'application/json','Accept-Encoding':'gzip','Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN']}
  request=urllib.request.Request(m.MS+path,data=json.dumps(body,ensure_ascii=False).encode(),headers=headers,method=method)
  try:
   with urllib.request.urlopen(request,timeout=90) as response:
    raw=response.read()
    if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
    result=json.loads(raw)
   save(self.db,label+':response',{'received':True,'result':result,'at':m.now()})
  except urllib.error.HTTPError as error:
   raw=error.read()
   try:
    if error.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
    detail=json.loads(raw)
   except Exception:detail={'http_status':error.code}
   save(self.db,label+':response',{'received':True,'http_status':error.code,'detail':detail,'at':m.now()})
  except (TimeoutError,urllib.error.URLError):
   save(self.db,label+':response',{'received':False,'uncertain':True,'at':m.now()})
def main(mode):
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(ROOT+'config:v1')
 assert cfg and cfg['authorized'] and cfg['scope']=='single_document_currency_test'
 assert cfg['document_type']=='purchaseorder' and cfg['rub_per_cny']==12
 path='entity/purchaseorder/'+cfg['document_id']
 before=getdoc(t,path)
 currencies=b.fullrows(t,'entity/currency')
 defaults=[c for c in currencies if c.get('default')]
 assert len(defaults)==1 and defaults[0]['isoCode']=='RUB'
 source_currency=before.get('rate',{}).get('currency',{})
 if mode=='inspect':
  assert source_currency.get('isoCode')=='RUB' and b.D(before['rate'].get('value',1))==1
  plan=b.plan(before,before['positions']['rows'])
  linked=readlinks(t,before)
  payload={'status':'inspected','at':m.now(),'before':before,'before_sha256':b.digest(stable(before)),'linked_before':linked,'plan':plan,'currencies_before':currencies,'quantity':str(sum((b.D(p['quantity']) for p in before['positions']['rows']),Decimal(0))),'ms_writes':0}
  save(db,'inspection:v1',payload)
  print('Single-document inspection and recovery snapshot saved privately.')
  return
 result=db.get(ROOT+'result:v1')
 if result and result.get('status')=='verified':
  print('Single-document conversion already verified; no replay.')
  return
 inspection=db.get(ROOT+'inspection:v1');assert inspection and inspection['status']=='inspected'
 assert b.digest(stable(before))==inspection['before_sha256'],'Source changed after inspection'
 assert source_currency.get('isoCode')=='RUB'
 linked=readlinks(t,before)
 assert {p:money(v) for p,v in linked.items()}=={p:money(v) for p,v in inspection['linked_before'].items()},'Linked documents changed'
 plan=b.plan(before,before['positions']['rows'])
 assert plan==inspection['plan']
 w=NarrowWriter(db,path)
 cny=[c for c in currencies if c.get('isoCode')=='CNY' and not c.get('archived')]
 assert len(cny)<=1,'Ambiguous CNY currencies'
 if not cny:
  w.write_once('entity/currency','POST',{'name':'юань','fullName':'Китайский юань','code':'156','isoCode':'CNY','rate':12,'multiplicity':1,'indirect':False},'currency_intent:v1')
  currencies=b.fullrows(t,'entity/currency')
  cny=[c for c in currencies if c.get('isoCode')=='CNY' and not c.get('archived')]
 assert len(cny)==1 and not cny[0].get('default')
 body={'rate':{'currency':m.meta(cny[0]),'value':12},'positions':[]}
 for old,price in zip(before['positions']['rows'],plan['price_minor']):
  # Updating existing position IDs preserves the existing document structure.
  position={k:copy.deepcopy(old[k]) for k in ('id','quantity','discount','vat','vatEnabled','pack','slot','things') if k in old}
  position['assortment']=m.meta(old['assortment']);position['price']=int(price)
  body['positions'].append(position)
 if isinstance(before.get('overhead'),dict) and 'sum' in before['overhead']:
  body['overhead']={**before['overhead'],'sum':int(b.R(b.D(before['overhead']['sum'])/12))}
 fresh=getdoc(t,path)
 assert b.digest(stable(fresh))==inspection['before_sha256'],'Source changed just before mutation'
 save(db,'expected:v1',{'body':body,'plan':plan,'at':m.now()})
 w.write_once(path,'PUT',body,'document_intent:v1')
 after=getdoc(t,path);linked_after=readlinks(t,after);currencies_after=b.fullrows(t,'entity/currency')
 save(db,'readback:v1',{'after':after,'linked_after':linked_after,'currencies_after':currencies_after,'at':m.now()})
 assert next(c for c in currencies_after if c.get('default'))['id']==defaults[0]['id']
 assert next(c for c in currencies_after if c.get('default'))['isoCode']=='RUB'
 assert after['rate']['currency']['id']==cny[0]['id'] and b.D(after['rate'].get('value',1))==12
 assert b.D(after['sum'])==b.D(plan['actual_minor']),'Saved total mismatch'
 aa=after['positions']['rows'];bb=before['positions']['rows']
 assert len(aa)==len(bb)
 for old,new,price in zip(bb,aa,plan['price_minor']):
  for key in ('id','quantity','discount','vat','vatEnabled','pack','slot','things'):
   assert old.get(key)==new.get(key),'Position structure changed: '+key
  assert m.href(old['assortment'])==m.href(new['assortment'])
  assert b.D(new['price'])==b.D(price),'Saved unit price mismatch'
 for key in ('name','moment','description','applicable','vatEnabled','vatIncluded','externalCode','paymentPlannedMoment','deliveryPlannedMoment'):
  assert after.get(key)==before.get(key),'Header changed: '+key
 for key in ('agent','organization','store','state','contract','project'):
  assert m.href(after.get(key,{}))==m.href(before.get(key,{})),'Reference changed: '+key
 assert set(linked)==set(linked_after)
 assert {p:money(v) for p,v in linked.items()}=={p:money(v) for p,v in linked_after.items()},'Linked monetary values changed'
 # This selected order must preserve its value in the RUB accounting currency.
 assert b.D(after['sum'])*12==b.D(before['sum']),'Accounting-value mismatch'
 save(db,'result:v1',{'status':'verified','at':m.now(),'document_id':before['id'],'name':before['name'],'source_minor':before['sum'],'target_minor':plan['target_minor'],'actual_minor':after['sum'],'deviation_minor':plan['deviation_minor'],'positions':len(aa),'quantity':inspection['quantity'],'currency':'CNY','rate':12,'accounting_currency':'RUB','linked_documents_unchanged':True,'linked_documents':len(linked),'payedSum':after.get('payedSum'),'shippedSum':after.get('shippedSum'),'position_prices':[{'id':p['id'],'old_minor':old['price'],'new_minor':p['price']} for old,p in zip(bb,aa)]})
 print('Single explicitly authorized document conversion verified privately.')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('inspect','apply'));args=parser.parse_args()
 try:main(args.mode)
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:'+args.mode+':v1',{'status':'stopped','at':m.now(),'error':type(error).__name__,'detail':str(error)})
  except Exception:pass
  print('Single-document operation stopped; inspect private diagnostics before retry.')
  sys.exit(1)
