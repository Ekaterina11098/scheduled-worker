"""Inspect selected chain currency impact using MS GET requests only."""
import datetime,sys,traceback
import cny_single_document_test as s
b=s.b;m=s.m
P='currency_impact_readonly:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t)
 cfg=db.get(b.ROOT+'screenshot_chain:config:v1');assert cfg['read_only'] and len(cfg['documents'])==4
 docs={x['type']:s.getdoc(t,'entity/'+x['type']+'/'+x['id']) for x in cfg['documents']}
 save(db,'documents:v1',{'at':m.now(),'documents':docs})
 reports={}
 for typ in ('demand','salesreturn'):
  d=docs[typ];pp=d['positions']['rows'];assert len(pp)==1
  start=datetime.datetime.fromisoformat(d['moment']);end=start+datetime.timedelta(seconds=1)
  fr=start.strftime('%Y-%m-%d %H:%M:%S');to=end.strftime('%Y-%m-%d %H:%M:%S')
  filters=';'.join(k+'='+m.href(v) for k,v in [('product',pp[0]['assortment']),('counterparty',d['agent']),('organization',d['organization']),('store',d['store'])])
  params={'filter':filters,'momentFrom':fr,'momentTo':to}
  value=t.request(m.MS,'report/profit/byproduct',params=params)
  entities={}
  for kind in ('demand','salesreturn'):
   entities[kind]=b.fullrows(t,'entity/'+kind,{'filter':'moment>='+fr+';moment<='+to+';agent='+m.href(d['agent']),'expand':'positions'})
  reports[typ]={'params':params,'report':value,'same_window_documents':entities}
  save(db,'profit:'+typ+':v1',{'at':m.now(),**reports[typ]})
 agent=docs['demand']['agent'];agent_id=m.href(agent).split('/')[-1]
 cp=t.request(m.MS,'report/counterparty/'+agent_id)
 currencies=b.fullrows(t,'entity/currency')
 save(db,'result:v1',{'status':'complete','at':m.now(),'documents':docs,'profit_reports':reports,'counterparty_report':cp,'currencies':currencies,'ms_writes':0})
 print('Selected-chain currency impact read only; private reports saved.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(error),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only currency-impact inspection stopped; private diagnostics saved.');sys.exit(1)
