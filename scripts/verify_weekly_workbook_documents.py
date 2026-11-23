"""Read-only live verification of completed reviewed-workbook accounting."""
import collections,os,sys,traceback
from decimal import Decimal,ROUND_FLOOR
sys.path.insert(0,'scripts')
import fbs_document_chain as m
ROOT=os.environ['WEEKLY_MANUAL_ROOT']
class ReadOnly(m.Transport):
 def request(self,base,path,method='GET',body=None,params=None):
  if base==m.MS and method!='GET':raise m.Stop('This phase cannot change accounting documents')
  if base==m.WB:raise m.Stop('Marketplace access outside scope')
  return super().request(base,path,method,body,params)
t=ReadOnly();db=m.Cache(t);w=m.Worker(t,db,{})
def norm(x):return m.href(x).split('?')[0]
def rows(path,params=None):return w.ms_rows(path,params)
def doc(kind,ident):return t.request(m.MS,'entity/'+kind+'/'+ident)
def article(p):return (p['assortment'].get('article') or '').strip().casefold()
def positions(kind,ident,stock=False):
 out=[];offset=0
 while True:
  params={'expand':'assortment','limit':100,'offset':offset}
  if stock:params['fields']='stock'
  data=t.request(m.MS,'entity/'+kind+'/'+ident+'/positions',params=params);batch=data['rows'];out+=batch;offset+=len(batch)
  if offset==data['meta']['size']:return out
  assert batch and offset<data['meta']['size'],'Incomplete positions'
def progress(stage):db.put(ROOT+'final_verification_progress:v1',{'stage':stage,'at':m.now(),'run_id':os.environ.get('GITHUB_RUN_ID')})
def main():
 plan=db.get(ROOT+'manual_plan:v1');req=db.get(ROOT+'request:v1');result=db.get(ROOT+'documents:v1');prep=db.get(ROOT+'manual_prepare:v1');returns=db.get(ROOT+'return_documents:v1')
 assert req.get('writes_authorized') and req.get('status') not in ('cancelled','canceled','revoked')
 assert req['manual_plan_sha256']==plan['sha256']==result['source_sha256']==returns['source_sha256']
 assert not result.get('pending_write') and returns['status']=='complete'
 prefix='weekly-china-'+'-'.join(plan['report_ids'])+'-'
 entries={x['id']:x for x in result['documents']+returns['documents']}
 orders=[e for e in entries.values() if e['type']=='customerorder'];demands=[e for e in entries.values() if e['type']=='demand']
 assert len(orders)==len(demands)==1
 expected=[(r['article'],r['quantity']) for r in plan['selected']]
 checks=[];live={};pos={};returned=collections.Counter()
 progress('checking_order_demand_and_return_lines')
 for entry in entries.values():
  kind=entry['type'];d=doc(kind,entry['id']);ps=positions(kind,entry['id']);live[entry['id']]=d;pos[entry['id']]=ps
  assert d.get('applicable') is True and d['sum']==0 and all(p['price']==0 for p in ps)
  assert all(norm(d[k])==norm(prep[k]) for k in ('organization','agent','store'))
  assert norm(d.get('rate',{}).get('currency',{}))==norm(prep['currency'])
  if kind in ('customerorder','demand'):assert [(article(p),p['quantity']) for p in ps]==expected,'Source row sequence differs'
  else:
   assert [(article(p),p['quantity']) for p in ps]==[(r['article'],r['quantity']) for r in plan['orange'] if prep['basis'][r['article']]['id']==norm(d['demand']).split('/')[-1]]
   for p in ps:returned[article(p)]+=p['quantity']
   assert d['description']=='рыжие возвраты из '+plan['comment']
   basis=doc('demand',norm(d['demand']).split('/')[-1]);bps=positions('demand',basis['id'])
   assert basis.get('applicable') is True
   for p in ps:
    matches=[x for x in bps if article(x)==article(p)];assert matches
    assert p.get('vat',0) in {x.get('vat',0) for x in matches},'Return VAT differs from historical basis'
  found=rows('entity/'+kind,{'filter':'externalCode='+d['externalCode']});assert len(found)==1 and found[0]['id']==d['id']
  checks.append({'type':kind,'id':d['id'],'name':d['name'],'quantity':sum(p['quantity'] for p in ps),'positions':len(ps),'posted':True,'all_prices_zero':True,'comment':d.get('description'),'store':prep['store']['name'],'basis':norm(d.get('demand',{})) if kind=='salesreturn' else None})
 order=live[orders[0]['id']];demand=live[demands[0]['id']]
 assert [norm(x) for x in order.get('demands',[])]==[norm(demand)] and norm(demand['customerOrder'])==norm(order)
 states=t.request(m.MS,'entity/customerorder/metadata').get('states',[])
 assert any(s['name']=='Доставлен' and norm(s)==norm(order['state']) for s in states)
 assert order['name']==', '.join(plan['report_ids']) and order['description']==plan['comment']
 assert dict(returned)==plan['returns']
 progress('rechecking_live_demand_cost')
 valuation=[]
 for p in positions('demand',demand['id'],True):
  q=Decimal(str(p['quantity']));cost=Decimal(str(p.get('stock',{}).get('cost') or 0));assert q>0 and cost>0
  unit=(cost/q).to_integral_value(rounding=ROUND_FLOOR);valuation.append({'article':article(p),'quantity':str(q),'unit_price_kopecks':str(unit),'actual_stock_cost_kopecks':str(cost)})
 total=sum(Decimal(x['quantity'])*Decimal(x['unit_price_kopecks']) for x in valuation)/100
 return_rub=sum((Decimal(prep['return_costs'][a]['unit_kopecks'])/100).to_integral_value(rounding=ROUND_FLOOR)*q for a,q in plan['returns'].items())
 def money(v):return format(v,',.2f').replace(',',' ').replace('.',',')
 comment='Опт: '+money(total)+' руб − рыжие возвраты '+money(return_rub)+' руб = '+money(total-return_rub)+' руб'
 assert demand['description']==comment==result['demand_comment'],'Live demand comment mismatch'
 progress('checking_stock_and_report_duplicates')
 bulk=rows('report/stock/all',{'filter':'store='+norm(prep['store'])+';moment='+prep['moment']+';stockMode=all;quantityMode=all'})
 byid={norm(x):x for x in bulk};assert len(byid)==len(bulk)
 for a in plan['sales']:
  stock=byid.get(norm(prep['products'][a]),{});assert stock.get('stock',0)>=0 and stock.get('quantity',0)>=0,'Negative stock after demand'
 flt=';'.join(k+'='+norm(prep[k]) for k in ('organization','agent','store'))+';moment>='+plan['period_from']+' 00:00:00'
 for kind in ('customerorder','demand','salesreturn'):
  expected_ids={x['id'] for x in entries.values() if x['type']==kind};found_ids=set()
  for d in rows('entity/'+kind,{'filter':flt}):
   if d.get('externalCode','').startswith(prefix) or any(rid in d.get('name','')+' '+d.get('description','') for rid in plan['report_ids']) or plan['comment'] in d.get('description',''):found_ids.add(d['id'])
  assert found_ids==expected_ids,'Unexpected weekly document or missing document'
 result.update(status='complete',completed_at=m.now(),documents=[{'type':x['type'],'id':x['id'],'name':x['name']} for x in checks],checks=checks,valuation_positions=valuation,wholesale_rub=str(total),returns_rub=str(return_rub),net_rub=str(total-return_rub),sales_units=plan['sales_units'],return_units=plan['return_units'],all_prices_zero=True,all_posted=True,duplicate_check=True,source_order_preserved=True,negative_stock_check=True)
 db.put(ROOT+'documents:v1',result)
 db.put(ROOT+'execution:v1',{'status':'complete','completed_at':m.now(),'documents':result['documents'],'sales_units':plan['sales_units'],'return_units':plan['return_units'],'source_sha256':plan['sha256']})
 req.update(status='complete',completed_at=m.now());db.put(ROOT+'request:v1',req)
 error=db.get(ROOT+'manual_error:v1')
 if error:error.update(resolved=True,resolved_at=m.now(),resolution='All live documents independently reverified; existing return reused');db.put(ROOT+'manual_error:v1',error)
 progress('complete')
try:
 main();print('Live weekly accounting verification passed; results retained privately.')
except Exception as exc:
 try:db.put(ROOT+'final_verification_error:v1',{'at':m.now(),'error_type':type(exc).__name__,'error':str(exc)[:1200],'trace':[{'line':x.lineno,'function':x.name} for x in traceback.extract_tb(exc.__traceback__)],'run_id':os.environ.get('GITHUB_RUN_ID')})
 except Exception:pass
 print('Live weekly accounting verification stopped; private diagnostic saved.');raise SystemExit(1)
