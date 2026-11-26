"""Read-only trace of current stock source documents for one exact product."""
import collections,re,sys,traceback
import cny_document_rollout as r
b=r.b;m=b.m;P='gray_umbrella_cost_trace:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1');assert cfg and cfg['mode']=='read_only'
 href=cfg['product_href'];product=t.request(m.MS,href[len(m.MS):]);cc=b.fullrows(t,'entity/currency');stores=b.fullrows(t,'entity/store')
 reports={};errors=[]
 for label,path,params in (
  ('stock_all','report/stock/all',{'filter':'stockMode=all;quantityMode=all;product='+href}),
  ('stock_by_store','report/stock/bystore',{'filter':'stockMode=all;product='+href}),
  ('stock_sources','report/byoperations/stock',{'filter':'assortment='+href})):
  try:
   rows=b.fullrows(t,path,params);reports[label]=rows;save(db,label+':v1',{'at':m.now(),'rows':rows})
  except Exception as e:
   errors.append({'stage':label,'detail':str(e),'trace':traceback.format_exc()});save(db,label+':error:v1',errors[-1])
 refs=collections.defaultdict(set)
 def collect(v):
  if isinstance(v,dict):
   meta=v.get('meta',{});url=meta.get('href','').split('?')[0]
   match=re.fullmatch(re.escape(m.MS)+r'entity/(supply|enter|move|salesreturn|demand)/([0-9a-f-]+)',url)
   if match:refs[match[1]].add(match[2])
   for x in v.values():collect(x)
  elif isinstance(v,list):
   for x in v:collect(x)
 collect(reports.get('stock_sources',[]));refs['supply'].update(cfg['known_supply_ids'])
 documents={}
 for typ,ss in refs.items():
  ids=sorted(ss);documents[typ]={}
  for i in range(0,len(ids),50):documents[typ].update(r.live(t,typ,ids[i:i+50]))
  save(db,'documents:'+typ,{'at':m.now(),'documents':documents[typ]})
 lines=[]
 for typ,dd in documents.items():
  for d in dd.values():
   for p in r.rows(d):
    if m.href(p['assortment'])==href:
     lines.append({'type':typ,'id':d['id'],'name':d['name'],'moment':d['moment'],'applicable':d.get('applicable'),'rate':d.get('rate'),'document_sum_minor':d['sum'],'store':d.get('store'),'sourceStore':d.get('sourceStore'),'targetStore':d.get('targetStore'),'unit_minor':p.get('price'),'quantity':p['quantity'],'overhead':p.get('overhead'),'document_overhead':d.get('overhead')})
 save(db,'result:v1',{'status':'complete' if not errors else 'partial','at':m.now(),'product':product,'currencies':cc,'stores':stores,'reports':reports,'document_lines':lines,'errors':errors,'ms_writes':0})
 print('Read-only exact product cost trace saved privately; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only cost trace stopped; inspect private journal.');sys.exit(1)
