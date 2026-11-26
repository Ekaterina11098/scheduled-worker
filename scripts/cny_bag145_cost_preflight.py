"""Read-only preflight of exact bag stock cost and candidate incoming records."""
import collections,sys,traceback
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='bag145_cost_test:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cfg=db.get(b.ROOT+P+'config:v1');assert cfg and cfg['authorized']
 product=t.request(m.MS,cfg['product_href'][len(m.MS):]);assert product['article'].casefold()==cfg['article'].casefold()
 cc=b.fullrows(t,'entity/currency');base=next(c for c in cc if c.get('default'));assert base['id']==cfg['base_currency_id'] and base['isoCode']=='CNY'
 reports={}
 for label,path,params in (
 ('stock_all','report/stock/all',{'filter':'stockMode=all;quantityMode=all;product='+cfg['product_href']}),
 ('stock_by_store','report/stock/bystore',{'filter':'stockMode=all;product='+cfg['product_href']}),
 ('stock_sources','report/byoperations/stock',{'filter':'assortment='+cfg['product_href']})):
  reports[label]=b.fullrows(t,path,params)
  save(db,'preflight:'+label,{'at':m.now(),'rows':reports[label]})
 docs={};lines=[];conflicts=[]
 for entry in cfg['baseline']:
  typ=entry['type'];old=entry['document'];d=r.live(t,typ,[old['id']])[old['id']]
  docs.setdefault(typ,{})[d['id']]=d
  try:
   a.invariants(old,d)
   body,signature,plan=r.prepare(old,typ,d['rate']['currency'])
   assert r.signature(d,typ)==signature,'Live amounts differ from verified historical conversion plan'
   assert b.D(d['rate'].get('value',1))==12 and not d.get('payments')
   pp=[p for p in r.rows(d) if m.href(p['assortment'])==cfg['product_href']];assert len(pp)==1
   lines.append({'type':typ,'id':d['id'],'name':d['name'],'moment':d['moment'],'position_count':len(r.rows(d)),'sum_minor':d['sum'],'unit_minor':pp[0]['price'],'quantity':pp[0]['quantity'],'rate':d['rate'],'store':d.get('store')})
  except Exception as e:conflicts.append({'type':typ,'id':d['id'],'detail':str(e)})
 save(db,'preflight:v1',{'status':'complete' if not conflicts else 'review_required','at':m.now(),'documents':docs,'document_lines':lines,'reports':reports,'currencies':cc,'product':product,'conflicts':conflicts,'ms_writes':0})
 print('Exact selected bag incoming cost preflight saved privately; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:preflight:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Bag cost preflight stopped; inspect private diagnostics.');sys.exit(1)
