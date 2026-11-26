"""Read-only detailed inventory price and linked-adjustment review."""
import collections,sys,traceback
import cny_one_chain_align_test as a
r=a.r;b=a.b;m=a.m;P='inventory_currency_detail_review:'
def save(db,k,v):b.put(db,P+k,v)
def shape(d):
 return [{'id':p['id'],'assortment':m.href(p['assortment']),'quantity':r.number(p.get('quantity')),'calculatedQuantity':r.number(p.get('calculatedQuantity')),'correctionAmount':r.number(p.get('correctionAmount'))} for p in r.rows(d)]
def main():
 t=b.ReadOnly();db=m.Cache(t)
 audit=db.get(b.ROOT+'all_document_currency_audit_post_incoming:records:inventory:0')['rows']
 targets=sorted([d for d in audit if 'amount_equals_original_ruble_total' in d['flags']],key=lambda d:(d['moment'],d['name']))
 assert len(targets)==192
 original={}
 for o in (0,100,200):
  pp=db.get(b.ROOT+'backup_extra:inventory:'+str(o));assert b.digest(pp['rows'])==pp['sha256']
  original.update({d['id']:d for d in pp['rows']})
 stores={m.href(d):d['name'] for d in b.fullrows(t,'entity/store')}
 docs={};summary=[];refs=collections.defaultdict(set)
 for o in range(0,len(targets),25):
  part=targets[o:o+25];live=r.live(t,'inventory',[d['id'] for d in part]);docs.update(live)
  save(db,'inventories:'+str(o),{'at':m.now(),'documents':live})
  for x in part:
   d=live[x['id']];old=original[x['id']]
   plan=b.plan(d,r.rows(d))
   links=[]
   for kind in ('losses','enters'):
    for q in d.get(kind,[]):
     typ=q['meta']['type'];assert typ in ('loss','enter')
     i=m.href(q).split('/')[-1];refs[typ].add(i);links.append({'type':typ,'id':i})
   summary.append({'id':d['id'],'name':d['name'],'moment':d['moment'],'store':stores.get(m.href(d.get('store',{}))),'sum_minor':d['sum'],'target_minor':plan['target_minor'],'planned_minor':plan['actual_minor'],'deviation_minor':plan['deviation_minor'],'positions':len(r.rows(d)),'quantity_shape_matches_original':shape(old)==shape(d),'prices_match_original':[b.D(p['price']) for p in r.rows(d)]==[b.D(p['price']) for p in r.rows(old)],'zero_count_priced_rows':sum(b.D(p.get('quantity'))==0 and b.D(p.get('price'))!=0 for p in r.rows(d)),'links':links})
  save(db,'progress:v1',{'at':m.now(),'checked':len(summary),'total':len(targets),'ms_writes':0})
 linked={}
 for typ,ids in refs.items():
  linked[typ]={};ii=sorted(ids)
  for o in range(0,len(ii),50):
   part=r.live(t,typ,ii[o:o+50]);linked[typ].update(part);save(db,'linked:'+typ+':'+str(o),{'at':m.now(),'documents':part})
 for x in summary:
  x['linked_summary']=[]
  for ref in x['links']:
   d=linked[ref['type']][ref['id']]
   x['linked_summary'].append({'type':ref['type'],'id':d['id'],'name':d['name'],'sum_minor':d.get('sum'),'currency_href':r.currency(d),'rate':d.get('rate',{}).get('value',1),'positions':len(r.rows(d)),'quantity':r.number(sum(b.D(p.get('quantity')) for p in r.rows(d)))})
 # Prefer a small inventory with two positions and a linked loss as the concrete example.
 example=next((d for d in sorted(docs.values(),key=lambda d:d['moment']) if len(r.rows(d))==2 and d.get('losses') and b.D(d['sum'])>0),next(iter(docs.values())))
 plan=b.plan(example,r.rows(example));lines=[]
 for p,newprice in zip(r.rows(example),plan['price_minor']):
  href=m.href(p['assortment']);product=t.request(m.MS,href[len(m.MS):])
  lines.append({'name':product.get('name'),'article':product.get('article'),'quantity':p.get('quantity'),'calculatedQuantity':p.get('calculatedQuantity'),'correctionAmount':p.get('correctionAmount'),'price_minor':p['price'],'new_price_minor':newprice,'correctionSum':p.get('correctionSum')})
 save(db,'example:v1',{'at':m.now(),'inventory':example,'summary':next(d for d in summary if d['id']==example['id']),'lines':lines})
 save(db,'result:v1',{'status':'complete','at':m.now(),'documents':summary,'linked_counts':{k:len(v) for k,v in linked.items()},'quantity_drift':sum(not d['quantity_shape_matches_original'] for d in summary),'price_drift':sum(not d['prices_match_original'] for d in summary),'rounding_documents':sum(b.D(d['deviation_minor'])!=0 for d in summary),'zero_count_priced_rows':sum(d['zero_count_priced_rows'] for d in summary),'ms_writes':0})
 print('Inventory price and linked-adjustment review complete; MS writes zero; details private.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'at':m.now(),'detail':str(e),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only inventory review stopped; inspect private diagnostics.');sys.exit(1)
