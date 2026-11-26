"""Full read-only audit of customer returns, migration amounts and linked document rates."""
import collections,concurrent.futures,copy,sys,traceback
import cny_single_document_test as s
import cny_document_rollout as r
b=s.b;m=s.m
P='returns_all_audit:'
def save(db,k,v):b.put(db,P+k,v)
def ident(x):return m.href(x).split('?')[0].split('/')[-1] if x else None
def lines(d):return r.rows(d)
def shape(p):return (m.href(p.get('assortment',{})),r.number(p.get('quantity')),m.href(p.get('country',{})),str(p.get('gtd','')),str(p.get('trackingCodes','')))
def page_task(task):
 offset,count=task;t=b.ReadOnly();db=m.Cache(t)
 old=db.get(b.ROOT+P+'live:salesreturn:'+str(offset))
 if old:return old['documents']
 page=t.request(m.MS,'entity/salesreturn',params={'limit':100,'offset':offset,'order':'id,asc','expand':'positions'})
 assert page['meta']['size']==count and len(page['rows'])==min(100,count-offset)
 for d in page['rows']:
  pp=d.get('positions',{});rr=pp.get('rows',[])
  if len(rr)!=pp.get('meta',{}).get('size',0):rr=b.fullrows(t,'entity/salesreturn/'+d['id']+'/positions')
  if pp:d['positions']={**pp,'rows':rr}
 save(db,'live:salesreturn:'+str(offset),{'at':m.now(),'documents':page['rows']})
 return page['rows']
def read_group(task):
 typ,ids,index=task;t=b.ReadOnly();db=m.Cache(t);key='live:'+typ+':'+str(index)
 old=db.get(b.ROOT+P+key)
 if old:return old['documents'],old.get('errors',[])
 errors=[]
 try:docs=list(r.live(t,typ,ids).values())
 except Exception:
  docs=[]
  for i in ids:
   try:docs.append(s.getdoc(t,'entity/'+typ+'/'+i))
   except Exception as e:errors.append({'type':typ,'id':i,'detail':str(e)})
 save(db,key,{'at':m.now(),'documents':docs,'errors':errors})
 return docs,errors
def collect(db,typ,ids):
 ids=sorted(set(ids));out={};errors=[]
 tasks=[(typ,ids[i:i+100],i//100) for i in range(0,len(ids),100)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for docs,err in pool.map(read_group,tasks):
   out.update({d['id']:d for d in docs});errors+=err
   save(db,'progress:v1',{'status':'reading','stage':typ,'read':len(out),'total':len(ids),'errors':len(errors),'at':m.now()})
 return out,errors
def baseline_task(i):
 db=m.Cache(b.ReadOnly());x=db.get(b.ROOT+P+'baseline:'+str(i));assert x
 return x['documents']
def main():
 t=b.ReadOnly();db=m.Cache(t)
 assert not db.get(b.ROOT+P+'result:v1'),'Audit already finalized; do not mix new live state with this snapshot'
 started=m.now();count=t.request(m.MS,'entity/salesreturn',params={'limit':1})['meta']['size']
 save(db,'manifest:v1',{'status':'started','at':started,'return_count':count,'ms_writes':0})
 baseline={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for dd in pool.map(baseline_task,range(119)):baseline.update({d['id']:d for d in dd})
 returns={};errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for dd in pool.map(page_task,[(i,count) for i in range(0,count,100)]):
   returns.update({d['id']:d for d in dd})
   save(db,'progress:v1',{'status':'reading','stage':'salesreturn','read':len(returns),'total':count,'at':m.now()})
 assert len(returns)==count
 demands,err=collect(db,'demand',[ident(d['demand']) for d in returns.values() if d.get('demand')]);errors+=err
 orders,err=collect(db,'customerorder',[ident(d['customerOrder']) for d in demands.values() if d.get('customerOrder')]);errors+=err
 paymentids=collections.defaultdict(set)
 for d in list(returns.values())+list(demands.values())+list(orders.values()):
  for p in d.get('payments',[]):
   typ=p.get('meta',{}).get('type')
   if typ in ('paymentin','paymentout','cashin','cashout'):paymentids[typ].add(ident(p))
   else:errors.append({'type':'payment_link','id':ident(p),'detail':'Unsupported payment type'})
 payments={}
 for typ,ids in sorted(paymentids.items()):
  dd,err=collect(db,typ,ids);payments.update({(typ,i):d for i,d in dd.items()});errors+=err
 currencies=b.fullrows(t,'entity/currency');curmap={m.href(c):c for c in currencies};default=next(c for c in currencies if c.get('default'))
 fixed={x['return_id'] for x in db.get(b.ROOT+'returns233:scope:v1')['items']}
 for key in ('selected_chain_align:result:v1','two_line_return_align:result:v1','partial_return_chain_align:result:v1','second_two_line_return_align:result:v1'):
  x=db.get(b.ROOT+key)
  assert x and x['status']=='verified'
  for row in x['summary']:
   if row['type']=='salesreturn':fixed.add(row['id'])
 assert len(fixed)==237
 rate_docs={};records=[];yearstats={};flags=collections.Counter();states=collections.Counter()
 for ret in sorted(returns.values(),key=lambda d:(d['moment'],d['id'])):
  rid=ret['id'];old=baseline.get(rid);dem=demands.get(ident(ret.get('demand')));order=orders.get(ident((dem or {}).get('customerOrder')))
  issues=[];pp=lines(ret);dq=sum((b.D(p['quantity']) for p in pp),b.D(0));base_target=None;status='no_baseline'
  if old:
   plan=b.plan(old,lines(old));base_target=b.D(plan['actual_minor'])
   same_shape=len(pp)==len(lines(old)) and [shape(p) for p in pp]==[shape(p) for p in lines(old)]
   if not same_shape:issues.append('return_shape_changed_from_backup')
   if rid in fixed:status='confirmed_order_alignment'
   elif not pp and b.D(ret['sum'])==0:status='empty_zero'
   elif b.D(ret['sum'])==b.D(old['sum']) and b.D(old['sum'])!=base_target:status='unconverted_original_amount'
   elif b.D(ret['sum'])==base_target and [b.D(p['price']) for p in pp]==[b.D(x) for x in plan['price_minor']]:status='converted_original_target'
   elif b.D(ret['sum'])==0 and b.D(old['sum'])==0:status='zero_value'
   else:status='other_amount_requires_review'
  if status=='unconverted_original_amount':issues.append('return_not_divided_by_12')
  if status in ('other_amount_requires_review','no_baseline'):issues.append(status)
  if not dem:issues.append('missing_or_unreadable_demand')
  if dem:
   dm=collections.defaultdict(list)
   for p in lines(dem):dm[m.href(p['assortment'])].append(p)
   for p in pp:
    matches=dm.get(m.href(p['assortment']),[])
    if not matches:issues.append('return_product_absent_from_demand');continue
    available=sum((b.D(x['quantity']) for x in matches),b.D(0))
    returned=sum((b.D(x['quantity']) for x in pp if m.href(x['assortment'])==m.href(p['assortment'])),b.D(0))
    if returned>available:issues.append('return_quantity_exceeds_demand')
    if not any(b.D(p['price'])==b.D(x['price']) and b.D(p.get('discount'))==b.D(x.get('discount')) for x in matches):issues.append('return_price_differs_from_demand')
    if not any(m.href(p.get('country',{}))==m.href(x.get('country',{})) and p.get('gtd')==x.get('gtd') for x in matches):issues.append('return_country_or_gtd_differs')
   if order:
    om=collections.defaultdict(list)
    for p in lines(order):om[m.href(p['assortment'])].append(p)
    for p in lines(dem):
     if not any(b.D(p['price'])==b.D(x['price']) and b.D(p.get('discount'))==b.D(x.get('discount')) for x in om.get(m.href(p['assortment']),[])):issues.append('demand_price_differs_from_order')
   else:issues.append('missing_or_unreadable_order')
  linked=[]
  for basis_type,d in [('salesreturn',ret),('demand',dem),('customerorder',order)]:
   if not d:continue
   for p in d.get('payments',[]):
    typ=p['meta']['type'];pay=payments.get((typ,ident(p)))
    if not pay:issues.append('unreadable_payment');continue
    linked.append(pay)
    ops=pay.get('operations',[])
    own=[x for x in ops if ident(x)==d['id']]
    if not own:issues.append('payment_reverse_link_missing')
    elif len(ops)==1 and b.D(own[0].get('linkedSum'))!=b.D(d['sum']):issues.append('single_payment_allocation_differs_from_basis')
  chain=[('salesreturn',ret)]+([('demand',dem)] if dem else [])+([('customerorder',order)] if order else [])
  chain += [(p['meta']['type'],p) for p in linked]
  for typ,d in chain:
   cur=curmap.get(r.currency(d),{});rate=b.D(d.get('rate',{}).get('value',1))
   if cur.get('isoCode')!='CNY':issues.append('chain_currency_not_cny')
   if default.get('isoCode')=='CNY' and cur.get('isoCode')=='CNY' and (rate!=1 or r.currency(d)!=m.href(default)):
    issues.append('chain_currency_reference_or_rate_not_base')
    rate_docs[(typ,d['id'])]={'type':typ,'id':d['id'],'name':d['name'],'moment':d['moment'],'sum_minor':d['sum'],'rate':str(rate),'currency_id':ident(d['rate']['currency']),'currency':cur.get('isoCode'),'accounting_minor':str(b.D(d['sum'])*rate),'currency_reference_not_base':r.currency(d)!=m.href(default)}
  issues=sorted(set(issues));flags.update(issues);states.update([status]);year=ret['moment'][:4]
  if year not in yearstats:yearstats[year]={'returns':0,'unconverted':0,'confirmed_aligned':0,'empty_zero':0,'issues':0}
  ys=yearstats[year];ys['returns']+=1;ys['unconverted']+=status=='unconverted_original_amount';ys['confirmed_aligned']+=rid in fixed;ys['empty_zero']+=status=='empty_zero';ys['issues']+=bool(issues)
  records.append({'id':rid,'name':ret['name'],'moment':ret['moment'],'status':status,'confirmed_alignment':rid in fixed,'sum_minor':ret['sum'],'original_minor':old.get('sum') if old else None,'original_target_minor':str(base_target) if base_target is not None else None,'positions':len(pp),'quantity':str(dq),'rate':str(b.D(ret.get('rate',{}).get('value',1))),'currency_id':ident(ret['rate']['currency']),'demand_id':dem.get('id') if dem else None,'demand_name':dem.get('name') if dem else None,'demand_sum_minor':dem.get('sum') if dem else None,'demand_rate':str(b.D(dem.get('rate',{}).get('value',1))) if dem else None,'order_id':order.get('id') if order else None,'order_name':order.get('name') if order else None,'order_sum_minor':order.get('sum') if order else None,'order_rate':str(b.D(order.get('rate',{}).get('value',1))) if order else None,'payment_count':len({p['id'] for p in linked}),'issues':issues})
 for i in range(0,len(records),100):save(db,'records:'+str(i//100),{'rows':records[i:i+100]})
 rates=list(rate_docs.values())
 for i in range(0,len(rates),100):save(db,'rates:'+str(i//100),{'rows':rates[i:i+100]})
 final_count=t.request(m.MS,'entity/salesreturn',params={'limit':1})['meta']['size']
 result={'status':'complete' if not errors and count==final_count else 'complete_with_limits','started_at':started,'finished_at':m.now(),'count':count,'final_count':final_count,'baseline_count':len(baseline),'linked_demands':len(demands),'linked_orders':len(orders),'linked_payments':len(payments),'states':dict(states),'issue_counts':dict(flags),'by_year':yearstats,'rate_document_count':len(rates),'rate_document_types':dict(collections.Counter(x['type'] for x in rates)),'errors':errors,'ms_writes':0,'confirmed_alignment_count':sum(x['confirmed_alignment'] for x in records)}
 save(db,'result:v1',result)
 print('Full read-only return audit completed; private results saved. No MS writes.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  try:save(m.Cache(b.ReadOnly()),'error:v1',{'status':'stopped','at':m.now(),'detail':str(error),'trace':traceback.format_exc()})
  except Exception:pass
  print('Read-only return audit stopped; inspect private diagnostics.');sys.exit(1)
