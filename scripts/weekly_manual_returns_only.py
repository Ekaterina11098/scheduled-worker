"""Complete authorized workbook returns independently of a stock-blocked shipment."""
import collections,datetime,os,sys
sys.path.insert(0,'scripts')
import fbs_document_chain as m
ROOT=os.environ['WEEKLY_MANUAL_ROOT'];assert ROOT.startswith('weekly_report_review:china:')
t=m.Transport();db=m.Cache(t);w=m.Worker(t,db,{})
plan=db.get(ROOT+'manual_plan:v1');prep=db.get(ROOT+'manual_prepare:v1');prefix='weekly-china-'+'-'.join(plan['report_ids'])+'-'
result=db.get(ROOT+'return_documents:v1') or {'status':'checking','documents':[],'source_sha256':plan['sha256'],'started_at':m.now()}
def permission():
 request=db.get(ROOT+'request:v1') or {}
 assert request.get('writes_authorized') and request.get('status') not in ('cancelled','canceled','revoked') and request.get('manual_plan_sha256')==plan['sha256']
def norm(x):return m.href(x).split('?')[0]
def rows(path,params=None):return w.ms_rows(path,params)
def positions(kind,uid):return rows('entity/'+kind+'/'+uid+'/positions',{'expand':'assortment'})
def art(p):return (p['assortment'].get('article') or '').strip().casefold()
def counts(ps):
 c=collections.Counter()
 for p in ps:c[art(p)]+=p['quantity']
 return c
def save():db.put(ROOT+'return_documents:v1',result)
def progress(stage):db.put(ROOT+'manual_returns_progress:v1',{'stage':stage,'at':m.now(),'run_id':os.environ.get('GITHUB_RUN_ID')})
def main():
 permission();assert result['source_sha256']==plan['sha256'] and plan['authorized']
 assert not result.get('pending_write'),'Previous return write outcome requires reconciliation'
 progress('rechecking_return_metadata')
 current={}
 for k in ('organization','agent','store','currency'):
  current[k]=t.request(m.MS,norm(prep[k])[len(m.MS):]);assert current[k]['id']==prep[k]['id'] and not current[k].get('archived')
 assert current['store']['name']==plan['expected_store_name'] and current['currency']['isoCode']=='RUB'
 products={}
 for r in plan['orange']:
  a=r['article'];products[a]=t.request(m.MS,norm(prep['products'][a])[len(m.MS):]);assert products[a]['article'].strip().casefold()==a and not products[a].get('archived')
 groups={}
 for r in plan['orange']:groups.setdefault(prep['basis'][r['article']]['id'],[]).append(r)
 progress('rechecking_return_capacity')
 common={k:m.meta(current[k]) for k in ('organization','agent','store')}
 moment=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
 common.update(applicable=True,moment=moment,rate={'currency':m.meta(current['currency'])})
 for ident,items in groups.items():
  basis=t.request(m.MS,'entity/demand/'+ident);assert basis.get('applicable') and all(norm(basis[k])==norm(current[k]) for k in ('organization','agent','store'))
  ext=prefix+'return-'+ident;found=rows('entity/salesreturn',{'filter':'externalCode='+ext});assert len(found)<=1
  if found:d=found[0]
  else:
   cap=counts(positions('demand',ident));used=collections.Counter()
   for ref in basis.get('returns',[]):
    existing=t.request(m.MS,norm(ref)[len(m.MS):]);used.update(counts(positions('salesreturn',existing['id'])))
   for r in items:assert cap[r['article']]-used[r['article']]>=r['quantity']
   template=t.request(m.MS,'entity/salesreturn/new','PUT',{'demand':m.meta(basis)});tp=template['positions']['rows']
   assert len(tp)==template['positions'].get('meta',{}).get('size',len(tp))
   ps=[]
   for r in items:
    matches=[p for p in tp if norm(p['assortment'])==norm(products[r['article']]) and p['quantity']>=r['quantity']];assert matches,'Return template lacks requested assortment'
    vats={(p.get('vat',0),p.get('vatEnabled',template.get('vatEnabled',False))) for p in matches};assert len(vats)==1
    vat,enabled=next(iter(vats));ps.append({'quantity':r['quantity'],'price':0,'discount':0,'vat':vat,'vatEnabled':enabled,'assortment':m.meta(products[r['article']])})
   permission()
   assert db.claim(ROOT+'return_claim:'+ident,{'at':m.now(),'run_id':os.environ.get('GITHUB_RUN_ID'),'source_sha256':plan['sha256']}),'Previous return execution claim requires reconciliation'
   result.update(status='creating',pending_write={'externalCode':ext,'at':m.now()});save();progress('creating_return')
   body={**common,'vatEnabled':template.get('vatEnabled',False),'vatIncluded':template.get('vatIncluded',True),'externalCode':ext,'description':'рыжие возвраты из '+plan['comment'],'demand':m.meta(basis),'positions':ps}
   try:d=t.request(m.MS,'entity/salesreturn','POST',body)
   except Exception:
    result['status']='write_outcome_requires_reconciliation';save();raise
   result['pending_write']=None;save()
  d=t.request(m.MS,'entity/salesreturn/'+d['id']);ps=positions('salesreturn',d['id'])
  assert [(art(p),p['quantity']) for p in ps]==[(r['article'],r['quantity']) for r in items]
  assert d.get('applicable') is True and d['sum']==0 and all(p['price']==0 for p in ps)
  assert norm(d['demand'])==norm(basis) and all(norm(d[k])==norm(current[k]) for k in ('organization','agent','store'))
  assert d['description']=='рыжие возвраты из '+plan['comment']
  assert len(rows('entity/salesreturn',{'filter':'externalCode='+ext}))==1
  result['documents']=[x for x in result['documents'] if x['id']!=d['id']]+[{'type':'salesreturn','id':d['id'],'name':d['name'],'quantity':sum(p['quantity'] for p in ps),'articles':[art(p) for p in ps],'basis_id':ident,'basis_name':basis['name'],'posted':True,'all_prices_zero':True}]
  save()
 assert sum(x['quantity'] for x in result['documents'])==plan['return_units']
 result.update(status='complete',completed_at=m.now(),row_order_preserved=True,duplicate_check=True);save();progress('complete')
 request=db.get(ROOT+'request:v1');request['status']='shipment_blocked_returns_complete';db.put(ROOT+'request:v1',request)
try:
 main();print('Requested workbook return phase completed; results retained privately.')
except Exception as exc:
 import traceback
 try:db.put(ROOT+'manual_returns_error:v1',{'at':m.now(),'error_type':type(exc).__name__,'error':str(exc)[:1200],'trace':[{'line':x.lineno,'function':x.name} for x in traceback.extract_tb(exc.__traceback__)],'run_id':os.environ.get('GITHUB_RUN_ID')})
 except Exception:pass
 print('Requested workbook return phase stopped; private diagnostic saved.');raise SystemExit(1)
