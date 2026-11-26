"""Read-only catalogue purchase-price and stock valuation currency audit."""
import collections,sys,traceback
import cny_document_rollout as r
b=r.b;m=b.m;P='product_cost_currency_audit:'
def save(db,k,v):b.put(db,P+k,v)
def main():
 t=b.ReadOnly();db=m.Cache(t);cc=b.fullrows(t,'entity/currency');cm={m.href(c):c for c in cc};base=next(c for c in cc if c.get('default'))
 catalogue={};stats={};rows=[]
 manifest=db.get(b.ROOT+'backup_manifest:v1')
 for typ in ('product','bundle','variant','service'):
  old={}
  for i in range(0,manifest['auxiliary'][typ]['count'],100):
   part=db.get(b.ROOT+'backup_aux:'+typ+':'+str(i));assert part
   old.update({d['id']:d for d in part['rows']})
  current=[]
  for archived in ('false','true'):current+=b.fullrows(t,'entity/'+typ,{'filter':'archived='+archived})
  assert len({d['id'] for d in current})==len(current)
  catalogue[typ]=current;count=collections.Counter(total=len(current))
  for i in range(0,len(current),100):save(db,'catalogue:'+typ+':'+str(i),{'at':m.now(),'rows':current[i:i+100]})
  for d in current:
   bp=d.get('buyPrice',{});value=b.D(bp.get('value'));obp=old.get(d['id'],{}).get('buyPrice',{});ov=b.D(obp.get('value'))
   cur=cm.get(m.href(bp.get('currency',{})),{})
   state='zero' if value==0 else 'new_or_changed'
   if value>0:
    count['positive_purchase_price']+=1;count['purchase_price_'+cur.get('isoCode','unknown')]+=1
    if d['id'] in old and ov>0:
     if value==ov:state='same_numeric_as_RUB_baseline';count[state]+=1
     elif value==b.R(ov/12):state='matches_RUB_baseline_div12';count[state]+=1
   rows.append({'type':typ,'id':d['id'],'article':d.get('article'),'code':d.get('code'),'name':d.get('name'),'archived':d.get('archived'),'buy_price_minor':bp.get('value'),'buy_currency':cur.get('isoCode'),'buy_currency_id':cur.get('id'),'baseline_buy_minor':obp.get('value'),'baseline_div12_minor':int(b.R(ov/12)),'state':state,'cost_attributes':[x for x in d.get('attributes',[]) if any(w in x.get('name','').lower() for w in ('себесто','закуп'))]})
  stats[typ]=dict(count)
 for i in range(0,len(rows),100):save(db,'price_rows:'+str(i),{'at':m.now(),'rows':rows[i:i+100]})
 save(db,'catalogue_result:v1',{'status':'complete','at':m.now(),'currencies':cc,'default_currency':base,'counts':stats,'ms_writes':0})
 print('Read-only catalogue price audit complete; private results saved.')
 stock=[];stock_errors=[]
 try:
  stock=b.fullrows(t,'report/stock/all',{'filter':'stockMode=all;quantityMode=all'})
  for i in range(0,len(stock),100):save(db,'stock:'+str(i),{'at':m.now(),'rows':stock[i:i+100]})
 except Exception as e:stock_errors.append({'detail':str(e),'trace':traceback.format_exc()})
 heads={};head_errors=[]
 for typ in ('supply','enter'):
  try:
   dd=b.fullrows(t,'entity/'+typ);ct=collections.Counter()
   for d in dd:
    c=cm.get(r.currency(d),{});ct[c.get('isoCode','unknown')+':rate'+r.number(d.get('rate',{}).get('value',1))]+=1
   heads[typ]={'count':len(dd),'currency_rates':dict(ct)}
   for i in range(0,len(dd),100):save(db,'incoming_headers:'+typ+':'+str(i),{'at':m.now(),'documents':dd[i:i+100]})
  except Exception as e:head_errors.append({'type':typ,'detail':str(e)})
 examples=[{k:d.get(k) for k in ('meta','name','article','code','stock','reserve','quantity','price','sum')} for d in stock if b.D(d.get('price'))>0][:10]
 save(db,'result:v1',{'status':'complete' if not stock_errors and not head_errors else 'partial','at':m.now(),'catalogue_counts':stats,'default_currency':base,'stock_rows':len(stock),'positive_stock_cost_rows':sum(b.D(d.get('price'))>0 for d in stock),'stock_examples':examples,'stock_errors':stock_errors,'incoming_document_headers':heads,'incoming_header_errors':head_errors,'ms_writes':0})
 print('Read-only cost-currency audit finished; inspect private completeness status; MS writes zero.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only cost audit stopped; inspect private diagnostics.');sys.exit(1)
