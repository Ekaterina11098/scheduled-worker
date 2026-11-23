"""Owner-authorized weekly accounting from a private reviewed workbook plan.

Operational data and execution state remain in the private cache. This worker
never calls marketplace APIs. Workbook line order is preserved, including repeats.
"""
import collections
import concurrent.futures
import datetime
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import os
import re
import sys
import time
sys.path.insert(0, 'scripts')
import fbs_document_chain as m

ROOT = os.environ['WEEKLY_MANUAL_ROOT']
assert re.fullmatch(r'weekly_report_review:china:\d{8}_\d{8}:', ROOT)
t = m.Transport()
db = m.Cache(t)
worker = m.Worker(t, db, {})
stage = 'initializing'
allowed_demand_ids = set()
allowed_basis_ids = set()
prefix = None
plan = None

def progress(value):
    global stage
    stage = value
    db.put(ROOT+'manual_progress:v1', {'stage':stage, 'at':m.now(), 'run_id':os.environ.get('GITHUB_RUN_ID')})

def permission():
    request = db.get(ROOT+'request:v1') or {}
    assert request.get('writes_authorized') is True and request.get('status') not in ('cancelled','canceled','revoked'), 'Authorization revoked'
    assert request.get('manual_plan_sha256') == plan['sha256'], 'Workbook authorization changed'

class Scoped(m.Transport):
    def request(self, base, path, method='GET', body=None, params=None):
        if base == m.WB:
            raise m.Stop('Marketplace access outside workbook scope')
        if base == m.MS and method != 'GET':
            permission()
            valid = (method == 'POST' and path in ('entity/customerorder','entity/demand','entity/salesreturn') and (body or {}).get('externalCode','').startswith(prefix))
            valid |= (method == 'PUT' and path == 'entity/salesreturn/new' and norm((body or {}).get('demand',{})).split('/')[-1] in allowed_basis_ids)
            valid |= (method == 'PUT' and path in {'entity/demand/'+i for i in allowed_demand_ids} and set(body or {}) == {'description'})
            if not valid:
                raise m.Stop('Write outside authorized weekly scope')
        return super().request(base, path, method, body, params)

def norm(value):
    return m.href(value).split('?')[0]

def rows(path, params=None):
    return worker.ms_rows(path, params)

def doc(kind, ident):
    return t.request(m.MS, 'entity/'+kind+'/'+ident)

def positions(kind, ident, stock=False):
    result=[];offset=0
    while True:
        params={'expand':'assortment','limit':100,'offset':offset}
        if stock:params['fields']='stock'
        data=t.request(m.MS,'entity/'+kind+'/'+ident+'/positions',params=params)
        batch=data['rows'];result+=batch;offset+=len(batch)
        if offset == data['meta']['size']:return result
        assert batch and offset < data['meta']['size'], 'Incomplete positions'

def article(p):
    return str(p['assortment'].get('article') or '').strip().casefold()

def counts(ps):
    result=collections.Counter()
    for p in ps:result[article(p)]+=p['quantity']
    return dict(result)

def sequence(ps):
    return [(article(p), p['quantity']) for p in ps]

def main():
    global t, worker, prefix, plan
    plan=db.get(ROOT+'manual_plan:v1') or {}
    assert plan.get('authorized') is True and plan.get('source')=='owner manually adjusted workbook'
    assert plan['sales_units']>0 and plan['return_units']==sum(plan['returns'].values())
    permission()
    assert len(plan['selected'])==plan['sales_units'] and all(x['quantity']==1 for x in plan['selected'])
    assert dict(collections.Counter(x['article'] for x in plan['selected']))==plan['sales']
    assert len({x['rrdId'] for x in plan['selected']+plan['orange']})==len(plan['selected'])+len(plan['orange'])
    assert not ({x['rrdId'] for x in plan['selected']} & {x['rrdId'] for x in plan['excluded_green']})
    prefix='weekly-china-'+'-'.join(plan['report_ids'])+'-'
    t=Scoped();worker=m.Worker(t,db,{})
    previous=db.get(plan['previous_configuration_key'])
    assert previous and previous.get('status') in ('ready','complete','prepared')
    prep={'status':'reading','at':m.now(),'source_sha256':plan['sha256'],'products':{},'basis':{},'return_costs':{},'duplicates':[]}
    def saveprep():db.put(ROOT+'manual_prepare:v1',prep)
    progress('reading_live_metadata')
    for k in ('organization','agent','store','currency'):
        prep[k]=t.request(m.MS,norm(previous[k])[len(m.MS):])
        assert prep[k]['id']==previous[k]['id'] and not prep[k].get('archived',False)
    assert prep['store']['name']==plan['expected_store_name'] and prep['currency']['isoCode']=='RUB'
    local=datetime.timezone(datetime.timedelta(hours=3))
    moment=datetime.datetime.now(local).strftime('%Y-%m-%d %H:%M:%S')
    prep['moment']=moment
    scope_filter=';'.join(k+'='+norm(prep[k]) for k in ('organization','agent','store'))
    progress('checking_duplicate_documents')
    for kind in ('customerorder','demand','salesreturn'):
        for d in rows('entity/'+kind,{'filter':scope_filter+';moment>='+plan['period_from']+' 00:00:00'}):
            if any(rid in d.get('name','')+' '+d.get('description','') for rid in plan['report_ids']) or plan['comment'] in d.get('description','') or d.get('externalCode','').startswith(prefix):
                prep['duplicates'].append({'type':kind,'id':d['id'],'name':d['name'],'externalCode':d.get('externalCode'),'description':d.get('description')})
    existing=db.get(ROOT+'documents:v1')
    if existing and existing.get('status')=='complete':
        assert existing.get('source_sha256')==plan['sha256']
        for entry in existing['documents']:
            d=doc(entry['type'],entry['id']);assert d.get('applicable') and d.get('sum')==0
        progress('previous_completion_reconfirmed');return
    prior_returns=db.get(ROOT+'return_documents:v1') or {}
    if prior_returns.get('status')=='complete':
        assert prior_returns.get('source_sha256')==plan['sha256']
        permitted={x['id']:x for x in prior_returns['documents']}
        unexplained=[]
        for entry in prep['duplicates']:
            if entry['type']=='salesreturn' and entry['id'] in permitted and entry.get('externalCode','').startswith(prefix+'return-'):
                d=doc('salesreturn',entry['id']);ps=positions('salesreturn',entry['id'])
                expected=permitted[entry['id']]
                assert d.get('applicable') and d['sum']==0 and all(p['price']==0 for p in ps)
                assert [article(p) for p in ps]==expected['articles'] and sum(p['quantity'] for p in ps)==expected['quantity']
            else:unexplained.append(entry)
        prep['verified_prior_returns']=prior_returns['documents'];prep['duplicates']=unexplained
    assert not prep['duplicates'], 'Existing documents require reconciliation; no new writes'
    assert not existing or not existing.get('pending_write'), 'Uncertain previous write requires reconciliation'
    saveprep()
    progress('reading_products')
    wanted=list(dict.fromkeys(x['article'] for x in plan['selected']+plan['orange']))
    def getproduct(a):
        rt=m.Transport();rw=m.Worker(rt,None,{})
        return a,rw.ms_rows('entity/product',{'filter':'article='+a+';archived=false'})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for a,ps in pool.map(getproduct,wanted):
            assert len(ps)==1 and ps[0]['article'].strip().casefold()==a, 'Missing or ambiguous product'
            prep['products'][a]=ps[0]
    saveprep()
    products=prep['products']
    def checkstock():
        progress('checking_fresh_stock')
        bulk=rows('report/stock/all',{'filter':'store='+norm(prep['store'])+';moment='+moment+';stockMode=all;quantityMode=all'})
        byid={norm(r):r for r in bulk};assert len(byid)==len(bulk)
        current=t.request(m.MS,'report/stock/bystore/current',params={'stockType':'freeStock','include':'zeroLines'})
        assert isinstance(current,list)
        free={(x['storeId'],x['assortmentId']):x['freeStock'] for x in current}
        exceptions=[]
        for a,q in plan['sales'].items():
            s=byid.get(norm(products[a]),{});f=free.get((prep['store']['id'],products[a]['id']))
            if s.get('stock',0)<q or s.get('quantity',0)<q or s.get('price',0)<=0 or type(f) not in (int,float) or f<q:
                exceptions.append({'article':a,'needed':q,'stock':s.get('stock',0),'available':s.get('quantity',0),'free':f,'unit_cost_kopecks':s.get('price')})
        prep.update(stock_exceptions=exceptions,fresh_stock_at=m.now());saveprep();return byid
    stock=checkstock()
    progress('finding_historical_return_bases')
    # Latest earlier posted demand with enough unreturned quantity owns each return.
    for d in rows('entity/demand',{'filter':scope_filter+';moment<='+moment,'order':'moment,desc'}):
        if len(prep['basis'])==len(plan['returns']):break
        if not d.get('applicable'):continue
        if any(rid in d.get('name','')+' '+d.get('description','') for rid in plan['report_ids']):continue
        ps=positions('demand',d['id']);cap=counts(ps)
        candidates={a for a,q in plan['returns'].items() if a not in prep['basis'] and cap.get(a,0)>=q}
        if not candidates:continue
        detail=doc('demand',d['id']);used=collections.Counter()
        for ref in detail.get('returns',[]):
            r=t.request(m.MS,norm(ref)[len(m.MS):])
            if r.get('externalCode')==prefix+'return-'+d['id']:continue
            used.update(counts(positions('salesreturn',r['id'])))
        for a in candidates:
            if cap[a]-used[a]>=plan['returns'][a]:
                prep['basis'][a]={'id':d['id'],'name':d['name'],'moment':d['moment'],'capacity':cap[a],'returned':used[a]}
        saveprep()
    assert set(prep['basis'])==set(plan['returns']), 'No eligible historical return basis'
    groups={}
    for r in plan['orange']:
        a=r['article'];basis=prep['basis'][a];allowed_basis_ids.add(basis['id'])
        groups.setdefault(basis['id'],[]).append(r)
        price=Decimal(str(stock.get(norm(products[a]),{}).get('price') or 0));source='current FBO stock'
        if price<=0:
            hp=[p for p in positions('demand',basis['id'],True) if article(p)==a]
            units={Decimal(str(p.get('stock',{}).get('cost') or 0))/Decimal(str(p['quantity'])) for p in hp if p['quantity']>0}
            assert len(units)==1 and next(iter(units))>0,'Missing or ambiguous historical return cost'
            price=next(iter(units));source='historical demand '+basis['name']
        prep['return_costs'][a]={'unit_kopecks':str(price),'source':source,'at':m.now()}
    prep['status']='blocked' if prep['stock_exceptions'] else 'ready';saveprep()
    if prep['stock_exceptions']:
        progress('blocked_insufficient_stock');return
    permission()
    assert db.claim(ROOT+'manual_execution_claim:v1',{'at':m.now(),'run_id':os.environ.get('GITHUB_RUN_ID'),'source_sha256':plan['sha256']}), 'Prior execution claim requires reconciliation'
    result={'status':'ready','source_sha256':plan['sha256'],'source_library_file_id':plan['library_file_id'],'documents':[],'started_at':m.now(),'source_order_preserved':True}
    def save():db.put(ROOT+'documents:v1',result)
    save()
    common={k:m.meta(prep[k]) for k in ('organization','agent','store')}
    common.update(applicable=True,moment=moment,vatEnabled=True,vatIncluded=True,rate={'currency':m.meta(prep['currency'])})
    states=[s for s in t.request(m.MS,'entity/customerorder/metadata').get('states',[]) if s['name']=='Доставлен'];assert len(states)==1
    def makepos(r):return {'quantity':r['quantity'],'price':0,'discount':0,'vat':0,'assortment':m.meta(products[r['article']])}
    def ensure(kind,tag,body,expected):
        permission();ext=prefix+tag
        found=rows('entity/'+kind,{'filter':'externalCode='+ext});assert len(found)<=1
        if found:d=found[0]
        else:
            assert not result.get('pending_write'), 'Uncertain write requires reconciliation'
            result.update(status='creating',pending_write={'kind':kind,'externalCode':ext,'at':m.now()});save()
            try:d=t.request(m.MS,'entity/'+kind,'POST',{**body,'externalCode':ext})
            except Exception:
                result['status']='write_outcome_requires_reconciliation';save();raise
            result['pending_write']=None;save()
        if kind=='demand':allowed_demand_ids.add(d['id'])
        ps=positions(kind,d['id'])
        assert all(norm(d.get(k,{}))==norm(prep[k]) for k in ('organization','agent','store'))
        assert norm(d.get('rate',{}).get('currency',{}))==norm(prep['currency'])
        assert d.get('applicable') is True and d['sum']==0 and all(p['price']==0 for p in ps)
        assert sequence(ps)==[(r['article'],r['quantity']) for r in expected], 'Document line order differs from workbook'
        entry={'type':kind,'id':d['id'],'name':d['name']}
        if entry not in result['documents']:result['documents'].append(entry)
        save();return d
    progress('creating_order')
    name=', '.join(plan['report_ids']);assert not rows('entity/customerorder',{'filter':'name='+name})
    order=ensure('customerorder','order',{**common,'name':name,'description':plan['comment'],'state':m.meta(states[0]),'positions':[makepos(r) for r in plan['selected']]},plan['selected'])
    assert not doc('customerorder',order['id']).get('demands',[])
    stock=checkstock();assert not prep['stock_exceptions'], 'Stock changed before shipment'
    progress('creating_demand')
    demand=ensure('demand','demand',{**common,'description':plan['comment'],'customerOrder':m.meta(order),'positions':[makepos(r) for r in plan['selected']]},plan['selected'])
    progress('valuing_demand')
    valuation=[]
    for p in positions('demand',demand['id'],True):
        q=Decimal(str(p['quantity']));cost=Decimal(str(p.get('stock',{}).get('cost') or 0));assert cost>0
        unit=(cost/q).to_integral_value(rounding=ROUND_FLOOR)
        valuation.append({'article':article(p),'quantity':str(q),'unit_price_kopecks':str(unit),'actual_stock_cost_kopecks':str(cost)})
    total=sum(Decimal(p['quantity'])*Decimal(p['unit_price_kopecks']) for p in valuation)/100
    return_rub=sum((Decimal(prep['return_costs'][a]['unit_kopecks'])/100).to_integral_value(rounding=ROUND_FLOOR)*q for a,q in plan['returns'].items())
    def money(v):return format(v,',.2f').replace(',',' ').replace('.',',')
    comment='Опт: '+money(total)+' руб − рыжие возвраты '+money(return_rub)+' руб = '+money(total-return_rub)+' руб'
    result.update(valuation_positions=valuation,demand_comment=comment);save()
    t.request(m.MS,'entity/demand/'+demand['id'],'PUT',{'description':comment})
    progress('creating_returns_in_workbook_order')
    for ident,items in groups.items():
        basis=doc('demand',ident);assert basis.get('applicable')
        # Recheck capacity immediately before creating each return.
        cap=counts(positions('demand',ident));used=collections.Counter()
        for ref in basis.get('returns',[]):
            r=t.request(m.MS,norm(ref)[len(m.MS):])
            if r.get('externalCode')==prefix+'return-'+ident:continue
            used.update(counts(positions('salesreturn',r['id'])))
        for r in items:assert cap.get(r['article'],0)-used[r['article']]>=r['quantity']
        template=t.request(m.MS,'entity/salesreturn/new','PUT',{'demand':m.meta(basis)})
        tp=template['positions']['rows'];assert len(tp)==template['positions'].get('meta',{}).get('size',len(tp))
        rps=[]
        for r in items:
            matches=[p for p in tp if article(p)==r['article'] and p['quantity']>=r['quantity']]
            assert matches and len({(p.get('vat',0),p.get('vatEnabled',template.get('vatEnabled',False))) for p in matches})==1
            p=matches[0];rps.append({**makepos(r),'vat':p.get('vat',0),'vatEnabled':p.get('vatEnabled',template.get('vatEnabled',False))})
        body={**common,'vatEnabled':template.get('vatEnabled',False),'vatIncluded':template.get('vatIncluded',True),'description':'рыжие возвраты из '+plan['comment'],'demand':m.meta(basis),'positions':rps}
        ensure('salesreturn','return-'+ident,body,items)
    progress('verifying_final_documents')
    checks=[];returned=collections.Counter()
    for e in result['documents']:
        kind=e['type'];d=doc(kind,e['id']);ps=positions(kind,e['id'])
        assert d.get('applicable') is True and d['sum']==0 and all(p['price']==0 for p in ps)
        assert len(rows('entity/'+kind,{'filter':'externalCode='+d['externalCode']}))==1
        if kind in ('customerorder','demand'):
            assert sequence(ps)==[(r['article'],r['quantity']) for r in plan['selected']]
            if kind=='customerorder':assert norm(d['state'])==norm(states[0]) and [norm(x) for x in d.get('demands',[])]==[norm(demand)]
            else:assert norm(d['customerOrder'])==norm(order) and d['description']==comment
        else:
            ident=norm(d['demand']).split('/')[-1];assert sequence(ps)==[(r['article'],r['quantity']) for r in groups[ident]]
            returned.update(counts(ps));assert d['description']=='рыжие возвраты из '+plan['comment']
        checks.append({**e,'quantity':sum(p['quantity'] for p in ps),'positions':len(ps),'all_prices_zero':True,'posted':True,'store':prep['store']['name'],'comment':d.get('description'),'basis':norm(d.get('demand',{})) if kind=='salesreturn' else None})
    assert dict(returned)==plan['returns']
    result.update(status='complete',completed_at=m.now(),checks=checks,wholesale_rub=str(total),returns_rub=str(return_rub),net_rub=str(total-return_rub),sales_units=plan['sales_units'],return_units=plan['return_units'],all_prices_zero=True,all_posted=True,duplicate_check=True)
    save();db.put(ROOT+'execution:v1',{'status':'complete','completed_at':m.now(),'documents':result['documents'],'sales_units':plan['sales_units'],'return_units':plan['return_units'],'source_sha256':plan['sha256']})
    request=db.get(ROOT+'request:v1');request.update(status='complete',completed_at=m.now());db.put(ROOT+'request:v1',request)
    progress('complete')

try:
    main()
    print('Requested workbook accounting phase finished; results retained privately.')
except Exception as exc:
    try:db.put(ROOT+'manual_error:v1',{'at':m.now(),'stage':stage,'error_type':type(exc).__name__,'error':str(exc)[:1200],'run_id':os.environ.get('GITHUB_RUN_ID')})
    except Exception:pass
    print('Requested workbook accounting stopped; private diagnostic saved.')
    raise SystemExit(1)
