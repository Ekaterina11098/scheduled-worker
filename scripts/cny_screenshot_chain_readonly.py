"""Read one screenshot-selected document chain and currency settings. MS GET only."""
import sys
import cny_single_document_test as s
b=s.b;m=s.m
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+'screenshot_chain:config:v1')
 assert cfg and cfg['read_only'] and len(cfg['documents'])==4
 out=[];summary=[]
 for item in cfg['documents']:
  assert item['type'] in ('customerorder','demand','paymentin','salesreturn')
  d=s.getdoc(t,'entity/'+item['type']+'/'+item['id'])
  out.append(d);cur=d.get('rate',{}).get('currency',{})
  summary.append({'type':item['type'],'id':d['id'],'name':d['name'],'sum_minor':d['sum'],'currency':cur.get('isoCode'),'currency_id':cur.get('id'),'rate':d.get('rate',{}).get('value',1),'quantity':sum(p['quantity'] for p in d.get('positions',{}).get('rows',[])),'positions':[{'id':p['id'],'quantity':p['quantity'],'price':p['price'],'assortment':m.href(p['assortment'])} for p in d.get('positions',{}).get('rows',[])]})
 currencies=b.fullrows(t,'entity/currency')
 b.put(db,'screenshot_chain:readback:v1',{'status':'complete','at':m.now(),'documents':out,'summary':summary,'currencies':currencies,'ms_writes':0})
 print('Selected chain and currencies inspected read only; private results saved.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:b.put(m.Cache(b.ReadOnly()),'screenshot_chain:error:v1',{'status':'failed','at':m.now(),'detail':str(error)})
  except Exception:pass
  print('Read-only inspection stopped; private diagnostics saved.');sys.exit(1)
