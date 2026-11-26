"""Read-only historical source-stock investigation for an exact product."""
import datetime,re,collections,sys,traceback
import cny_document_rollout as r
b=r.b;m=b.m;P='gray_umbrella_cost_trace:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1');prior=db.get(b.ROOT+P+'result:v1')
 assert cfg and cfg['mode']=='read_only' and prior and prior['status']=='complete'
 moves=[d for d in prior['document_lines'] if d['type']=='move'];assert len(moves)==1
 move=moves[0];source=m.href(move['sourceStore']);moment=(datetime.datetime.strptime(move['moment'],'%Y-%m-%d %H:%M:%S.%f')-datetime.timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
 href=cfg['product_href'];reports={};errors=[]
 requests=(
  ('source_stock_before','report/stock/all',{'filter':'stockMode=all;quantityMode=all;product='+href+';store='+source,'moment':moment}),
  ('source_lots_before','report/byoperations/stock',{'filter':'assortment='+href+';store='+source+';moment='+moment}),
  ('source_turnover','report/turnover/byoperations',{'filter':'product='+href+';store='+source,'momentFrom':'2024-01-01 00:00:00','momentTo':move['moment'][:19]}),
  ('stock_at_move','report/stock/byoperation',{'operation.id':move['id']})
 )
 for label,path,params in requests:
  try:
   result=t.request(m.MS,path,params=params)
   if label=='source_lots_before':
    for row in result.get('rows',[]):
     assert m.href(row['store'])==source and row['moment'][:19]<=moment,'Historical filter not respected'
   reports[label]=result;save(db,label+':v1',{'at':m.now(),'result':result})
  except Exception as e:errors.append({'stage':label,'detail':str(e)});save(db,label+':error:v1',{'at':m.now(),'detail':str(e)})
 refs=collections.defaultdict(set)
 def collect(v):
  if isinstance(v,dict):
   url=v.get('meta',{}).get('href','').split('?')[0];match=re.fullmatch(re.escape(m.MS)+r'entity/(supply|enter|move|salesreturn|demand)/([0-9a-f-]+)',url)
   if match:refs[match[1]].add(match[2])
   for x in v.values():collect(x)
  elif isinstance(v,list):
   for x in v:collect(x)
 collect(reports.get('source_lots_before',{}))
 docs={}
 for typ,ss in refs.items():
  assert len(ss)<=50
  docs[typ]=r.live(t,typ,sorted(ss))
 save(db,'historical_result:v1',{'status':'complete' if not errors else 'partial','at':m.now(),'source_store':source,'before_moment':moment,'move':move,'reports':reports,'source_documents':docs,'errors':errors,'ms_writes':0})
 print('Read-only historical stock sources investigated; private results saved; quantities unchanged.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'historical_error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Historical cost investigation stopped; inspect private diagnostics.');sys.exit(1)
