"""Read audit and notes for the four explicitly selected chain documents."""
import sys
import cny_migration_backup_20261125 as b
m=b.m
def pages(t,path):
 rows=[];expected=None
 while True:
  page=t.request(m.MS,path,params={'limit':100,'offset':len(rows)})
  expected=page['meta'].get('size')
  rows+=page['rows']
  if expected is not None and len(rows)==expected:return {'rows':rows,'complete':True,'size':expected}
  if not page['rows'] or len(page['rows'])<100:return {'rows':rows,'complete':expected is None or len(rows)==expected,'size':expected}
  if len(rows)>=1000:return {'rows':rows,'complete':False,'size':expected}
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+'screenshot_chain:config:v1')
 assert cfg and cfg['read_only'] and len(cfg['documents'])==4
 sections=[]
 for item in cfg['documents']:
  assert item['type'] in ('customerorder','demand','paymentin','salesreturn')
  section={'type':item['type'],'id':item['id'],'at':m.now()}
  path='entity/'+item['type']+'/'+item['id']
  for resource in ('audit','notes'):
   try:section[resource]=pages(t,path+'/'+resource)
   except Exception as error:section[resource]={'error':str(error),'complete':False}
  sections.append(section)
  b.put(db,'screenshot_chain:audit:'+item['type'],section)
 b.put(db,'screenshot_chain:audit_result:v1',{'status':'complete','at':m.now(),'sections':[{'type':x['type'],'audit_count':len(x.get('audit',{}).get('rows',[])),'audit_complete':x.get('audit',{}).get('complete'),'audit_error':x.get('audit',{}).get('error'),'notes_count':len(x.get('notes',{}).get('rows',[]))} for x in sections],'ms_writes':0})
 print('Selected-chain audit and notes inspected read only; results private.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:b.put(m.Cache(b.ReadOnly()),'screenshot_chain:audit_error:v1',{'status':'failed','detail':str(error),'at':m.now()})
  except Exception:pass
  print('Read-only audit stopped; private diagnostics saved.');sys.exit(1)
