"""Consolidate repeated assortments in two existing authorized weekly documents."""
import collections,copy,hashlib,json,os,sys,traceback
from decimal import Decimal,ROUND_FLOOR
sys.path.insert(0,'scripts')
import fbs_document_chain as m
ROOT=os.environ['WEEKLY_MANUAL_ROOT'];assert ROOT.startswith('weekly_report_review:china:')
allowed={};t=m.Transport();db=m.Cache(t);w=m.Worker(t,db,{})
def permission():
 req=db.get(ROOT+'merge_request:v1') or {};owner=db.get(ROOT+'request:v1') or {}
 assert req.get('authorized') is True and req.get('status') not in ('cancelled','canceled','revoked')
 assert owner.get('writes_authorized') and owner.get('status') not in ('cancelled','canceled','revoked')
class Scoped(m.Transport):
 def request(self,base,path,method='GET',body=None,params=None):
  if base==m.WB:raise m.Stop('Marketplace access prohibited')
  if base==m.MS and method!='GET':
   permission();assert method=='PUT' and path in allowed,'Only the existing weekly order and demand may be updated'
   keys=set(body or {});assert keys=={'positions'} or (allowed[path]=='demand' and keys=={'description'}),'Mutation outside consolidation scope'
  return super().request(base,path,method,body,params)
def norm(x):return m.href(x).split('?')[0]
def rows(path,params=None):return w.ms_rows(path,params)
def doc(kind,uid):return t.request(m.MS,'entity/'+kind+'/'+uid)
def positions(kind,uid,stock=False):
 out=[];offset=0
 while True:
  params={'expand':'assortment','limit':100,'offset':offset}
  if stock:params['fields']='stock'
  data=t.request(m.MS,'entity/'+kind+'/'+uid+'/positions',params=params);out+=data['rows'];offset+=len(data['rows'])
  if offset==data['meta']['size']:return out
  assert data['rows'] and offset<data['meta']['size']
def article(p):return (p['assortment'].get('article') or '').strip().casefold()
def counts(ps):
 result=collections.Counter()
 for p in ps:result[article(p)]+=p['quantity']
 return dict(result)
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def progress(stage):db.put(ROOT+'merge_progress:v1',{'stage':stage,'at':m.now(),'run_id':os.environ.get('GITHUB_RUN_ID')})
def main():
 global t,w
 permission();plan=db.get(ROOT+'manual_plan:v1');report=db.get(ROOT+'documents:v1');prep=db.get(ROOT+'manual_prepare:v1');req=db.get(ROOT+'merge_request:v1')
 assert report['status']=='complete' and report['source_sha256']==plan['sha256']
 assert req['expected_units']==plan['sales_units']
 order_articles=list(dict.fromkeys(r['article'] for r in plan['selected']))
 expected_counts=plan['sales'];assert len(order_articles)==req['expected_unique_articles'] and sum(expected_counts.values())==req['expected_units']
 targets=[x for x in report['documents'] if x['type'] in ('customerorder','demand')];assert len(targets)==2
 targets.sort(key=lambda x:0 if x['type']=='customerorder' else 1)
 allowed.update({'entity/'+x['type']+'/'+x['id']:x['type'] for x in targets});t=Scoped();w=m.Worker(t,db,{})
 progress('reading_live_document_positions')
 baseline={};bodies={};return_snapshots={}
 for e in report['documents']:
  d=doc(e['type'],e['id']);ps=positions(e['type'],e['id'])
  assert d.get('applicable') is True and d['sum']==0 and all(p['price']==0 for p in ps)
  assert all(norm(d[k])==norm(prep[k]) for k in ('organization','agent','store'))
  if e['type']=='salesreturn':return_snapshots[e['id']]={'document':d,'positions':ps};continue
  assert counts(ps)==expected_counts,'Live quantities differ from reviewed workbook'
  groups=collections.OrderedDict()
  for p in ps:
   a=article(p);assert a in expected_counts
   for k in ('trackingCodes','things','marks','customsDeclaration'):
    assert not p.get(k),'Tracked or customs fields require special preservation'
   signature={k:p.get(k) for k in ('price','discount','vat','vatEnabled','pack')}
   if a not in groups:groups[a]={'first':p,'signature':signature,'quantity':0,'reserve':0}
   g=groups[a];assert norm(g['first']['assortment'])==norm(p['assortment']) and g['signature']==signature,'Conflicting repeated line attributes'
   g['quantity']+=p['quantity'];g['reserve']+=p.get('reserve',0)
  assert list(groups)==order_articles,'First appearance order differs from reviewed workbook'
  body=[]
  for a,g in groups.items():
   first=g['first'];p={'id':first['id'],'quantity':g['quantity'],'price':first['price'],'discount':first.get('discount',0),'vat':first.get('vat',0),'assortment':m.meta(first['assortment'])}
   if 'vatEnabled' in first:p['vatEnabled']=first['vatEnabled']
   if first.get('pack'):p['pack']=copy.deepcopy(first['pack'])
   if e['type']=='customerorder' and any('reserve' in x for x in ps):p['reserve']=g['reserve']
   body.append(p)
  baseline[e['id']]={'document':d,'positions':ps};bodies[e['id']]=body
 state={'status':'prepared','at':m.now(),'source_sha256':plan['sha256'],'expected_units':req['expected_units'],'expected_positions':len(order_articles),'before_positions':{e['type']:len(baseline[e['id']]['positions']) for e in targets},'documents':[],'snapshots':baseline,'return_snapshots':return_snapshots}
 db.put(ROOT+'merge_result:v1',state)
 def save():db.put(ROOT+'merge_result:v1',state)
 progress('checking_stock_before_merge')
 def stock_snapshot():
  bulk=rows('report/stock/all',{'filter':'store='+norm(prep['store'])+';moment='+prep['moment']+';stockMode=all;quantityMode=all'})
  byid={norm(x):x for x in bulk};assert len(byid)==len(bulk)
  out={}
  for a in order_articles:
   s=byid.get(norm(prep['products'][a]),{});out[a]={'stock':s.get('stock',0),'quantity':s.get('quantity',0)}
   assert out[a]['stock']>=0 and out[a]['quantity']>=0
  return out
 before_stock=stock_snapshot();state['stock_before']=before_stock;save()
 claim=db.get(ROOT+'merge_execution_claim:v1')
 assert claim is None,'Previous consolidation execution requires live reconciliation'
 assert db.claim(ROOT+'merge_execution_claim:v1',{'source_sha256':plan['sha256'],'at':m.now(),'run_id':os.environ.get('GITHUB_RUN_ID')})
 for e in targets:
  kind=e['type'];uid=e['id'];before=baseline[uid];progress('consolidating_'+kind)
  current=doc(kind,uid);current_ps=positions(kind,uid)
  assert current.get('updated')==before['document'].get('updated') and digest(current_ps)==digest(before['positions']),'Document edited concurrently'
  if len(current_ps)!=len(order_articles):
   state.update(status='updating',pending_write={'type':kind,'id':uid,'at':m.now()});save()
   try:t.request(m.MS,'entity/'+kind+'/'+uid,'PUT',{'positions':bodies[uid]})
   except Exception:
    state['status']='uncertain_update_requires_reconciliation';save();raise
   state['pending_write']=None;save()
  d=doc(kind,uid);ps=positions(kind,uid)
  assert len(ps)==len(order_articles) and [article(p) for p in ps]==order_articles and counts(ps)==expected_counts
  assert d['applicable'] is True and d['sum']==0 and all(p['price']==0 for p in ps)
  for k in ('name','moment','organization','agent','store','state','customerOrder','rate','description','vatEnabled','vatIncluded'):
   assert d.get(k)==before['document'].get(k),'Unrelated document field changed: '+k
  state['documents'].append({'type':kind,'id':uid,'name':d['name'],'positions':len(ps),'quantity':sum(p['quantity'] for p in ps),'posted':True,'all_prices_zero':True});save()
 progress('checking_consolidated_demand_cost')
 de=next(e for e in targets if e['type']=='demand');demand=doc('demand',de['id']);valuation=[]
 for p in positions('demand',de['id'],True):
  q=Decimal(str(p['quantity']));cost=Decimal(str(p.get('stock',{}).get('cost') or 0));assert cost>0 and q>0
  unit=(cost/q).to_integral_value(rounding=ROUND_FLOOR);valuation.append({'article':article(p),'quantity':str(q),'actual_stock_cost_kopecks':str(cost),'unit_price_kopecks':str(unit)})
 total=sum(Decimal(x['quantity'])*Decimal(x['unit_price_kopecks']) for x in valuation)/100
 return_rub=Decimal(report['returns_rub'])
 def money(x):return format(x,',.2f').replace(',',' ').replace('.',',')
 comment='Опт: '+money(total)+' руб − рыжие возвраты '+money(return_rub)+' руб = '+money(total-return_rub)+' руб'
 if demand['description']!=comment:
  permission();state['pending_write']={'type':'demand','id':de['id'],'field':'description','at':m.now()};save()
  t.request(m.MS,'entity/demand/'+de['id'],'PUT',{'description':comment});state['pending_write']=None;save()
 progress('verifying_consolidation')
 assert stock_snapshot()==before_stock,'Warehouse quantities changed across consolidation'
 checks=[]
 for e in report['documents']:
  d=doc(e['type'],e['id']);ps=positions(e['type'],e['id'])
  assert d.get('applicable') and d['sum']==0 and all(p['price']==0 for p in ps)
  if e['type']=='salesreturn':assert digest({'document':d,'positions':ps})==digest(return_snapshots[e['id']]),'Return document changed'
  else:assert len(ps)==len(order_articles) and [article(p) for p in ps]==order_articles and counts(ps)==expected_counts
  if e['type']=='demand':assert d['description']==comment
  assert len(rows('entity/'+e['type'],{'filter':'externalCode='+d['externalCode']}))==1
  checks.append({'type':e['type'],'id':d['id'],'name':d['name'],'positions':len(ps),'quantity':sum(p['quantity'] for p in ps),'all_prices_zero':True,'posted':True,'comment':d.get('description'),'store':prep['store']['name'],'basis':norm(d.get('demand',{})) if e['type']=='salesreturn' else None})
 order=doc('customerorder',targets[0]['id']);demand=doc('demand',de['id'])
 assert norm(demand['customerOrder'])==norm(order) and [norm(x) for x in order.get('demands',[])]==[norm(demand)]
 report.update(checks=checks,valuation_positions=valuation,wholesale_rub=str(total),net_rub=str(total-return_rub),demand_comment=comment,row_order_policy='first appearance in owner workbook',positions_consolidated=True,unique_sales_positions=len(order_articles),merge_completed_at=m.now())
 db.put(ROOT+'documents:v1',report)
 req.update(status='complete',completed_at=m.now());db.put(ROOT+'merge_request:v1',req)
 owner=db.get(ROOT+'request:v1');owner['row_order_policy']='first appearance in owner workbook; repeated products consolidated';db.put(ROOT+'request:v1',owner)
 state.update(status='complete',completed_at=m.now(),checks=checks,wholesale_rub=str(total),returns_rub=str(return_rub),net_rub=str(total-return_rub),old_wholesale_rub=report.get('wholesale_rub'),pending_write=None,returns_unchanged=True,quantities_unchanged=True,source_order_preserved=True);save();progress('complete')
try:
 main();print('Authorized position consolidation verified; private results saved.')
except Exception as exc:
 try:db.put(ROOT+'merge_error:v1',{'at':m.now(),'error_type':type(exc).__name__,'error':str(exc)[:1500],'trace':[{'line':x.lineno,'function':x.name} for x in traceback.extract_tb(exc.__traceback__)],'run_id':os.environ.get('GITHUB_RUN_ID')})
 except Exception:pass
 print('Authorized position consolidation stopped; private diagnostic saved.');raise SystemExit(1)
