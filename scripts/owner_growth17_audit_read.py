"""Scoped four-direction owner audit. Read only; no model, stock or WB mutations."""
import os,json,time,re,copy
from datetime import datetime,timezone,timedelta
from collections import Counter
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_advertising_v2 import http
from china_moysklad_read import Reader,BASE
from china_morning_readiness import published_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_growth_audit:2026-11-17:v1'
STORE='3c67619d-f25d-11ee-0a80-0c6f000a027a';WAREHOUSES=[1863255,854652,2126188]
def main():
 c=Cache();scope=c.get(ROOT+':scope');assert scope['status']=='authorized_read_only'and scope['owner_id']==5122667182
 assert c.create(ROOT+':claim',dict(status='collecting',at=stamp())),'Inspect existing stages, no duplicate collection'
 validate_identity(c,WB());io=type('ReadIO',(),dict(token=os.environ['WB_TOKEN_3']))()
 v=dict(status='collecting',observed_at=stamp(),errors={},wb_writes=0,moysklad_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 def stage(k,fn):
  try:v[k]=fn()
  except Exception as e:v['errors'][k]=type(e).__name__+': '+str(e)[:220]
  c.put(ROOT+':fresh',v)
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();p=u.path;body=kw.get('json')or{}
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:
   ok=(p.startswith('/rest/v1/')and m in('GET','POST','PATCH'))or(p=='/functions/v1/stock-ozon-read'and m=='POST'and body.get('path')in('/v4/posting/fbs/list','/v2/product/info/stocks-by-warehouse/fbs'))
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config'))or(m=='POST'and p in('/api/advert/v1/bids/min','/api/advert/v2/budget'))
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and p=='/api/v2/list/goods/filter'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=(m=='GET'and p in('/api/v3/orders','/api/v3/orders/new'))or(m=='POST'and(p=='/api/v3/orders/status'or p in('/api/v3/stocks/'+str(n)for n in WAREHOUSES)))
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/')
  elif u.hostname=='mcp.mpstats.io':ok=m=='POST'
  elif u.hostname=='card.wb.ru':ok=m=='GET'and p in('/cards/v4/detail','/cards/v2/detail')
  else:ok=False
  assert ok,'Audit forbids mutation or unrelated transport '+m+' '+str(u.hostname)+p
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(host,path,body=None,params=None,index=2):
  time.sleep(.65);h={'Authorization':os.environ['WB_TOKEN_'+str(index+1)]}
  r=requests.request('POST'if body is not None else'GET','https://'+host+path,headers=h,json=body,params=params,timeout=(10,45));r.raise_for_status();return r.json()
 class MS(Reader):
  products={}
  def pages(self,path,params):
   rows=super().pages(path,params)
   if path=='/entity/product':
    for r in rows:self.products[r['meta']['href'].split('?')[0]]=str(r.get('article','')).casefold()
   return rows
 reader=MS()
 try:
  stage('campaigns',lambda:dict(observed_at=stamp(),adverts=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,scope['read_campaign_ids'])))['adverts']))
  def minima():
   out={}
   for cp in v['campaigns']['adverts']:
    ids=[n['nm_id']for n in cp['nm_settings']if n['nm_id']in scope['nm_ids']]
    if ids:out[str(cp['id'])]=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=cp['id'],nm_ids=ids,payment_type='cpc',placement_types=['search'if cp['settings']['placements']['search']else'recommendation']))
   return dict(observed_at=stamp(),rows=out)
  stage('minimums',minima)
  def prices():
   goods=req('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',params=dict(limit=1000,offset=0))['data']['listGoods'];assert len(goods)<1000
   out=[]
   for nm in scope['nm_ids']:
    match=[x for x in goods if x['nmID']==nm];assert len(match)==1
    r=match[0];vals={z['discountedPrice']for z in r['sizes']};assert len(vals)==1 and r['currencyIsoCode4217']=='CNY'
    out.append(dict(nm_id=nm,article=r['vendorCode'],seller_price=next(iter(vals)),discount=r['discount'],base_prices=sorted({z['price']for z in r['sizes']}),size_ids=[z['sizeID']for z in r['sizes']],currency='CNY'))
   return dict(observed_at=stamp(),rows=out)
  stage('prices',prices)
  def stock():
   out=[];articles=[r['article']for r in v['prices']['rows']]
   for i in range(0,len(articles),20):out.append(reader.stock(articles[i:i+20],'msk'))
   assert all(x['coverage_complete']and x['warehouse_id']==STORE for x in out)
   return dict(observed_at=stamp(),warehouse_id=STORE,rows=sum([x['rows']for x in out],[]),coverage_complete=True)
  stage('stock',stock)
  stage('published',lambda:published_stock(io,v['prices'],scope['nm_ids']))
  def economic():
   x=model_rows(dict(products=scope['products'],prices=v['prices'],stock=v['stock'],fx=dict(rub_per_cny=scope['fx_rub_per_cny'])),c.get('china_agent:new_ad_economics_policy:v1'),c.get('china_agent:expected_profit_delivery_model:v1'))
   for nm,e in x['rows'].items():e.update(published_stock=v['published']['amounts'].get(nm),published_stock_observed_at=v['published']['observed_at'],fx_rub_per_cny=scope['fx_rub_per_cny'])
   return x
  stage('economics',economic)
  def buyer():
   errors=[]
   for version in (4,2):
    try:
     r=requests.get('https://card.wb.ru/cards/v'+str(version)+'/detail',params=dict(appType=1,curr='rub',dest=-1257786,spp=30,nm=';'.join(map(str,scope['nm_ids']))),timeout=(10,25));r.raise_for_status();j=r.json();products=j.get('products',j.get('data',{}).get('products'))
     assert isinstance(products,list)and {x['id']for x in products}==set(scope['nm_ids'])
     return dict(observed_at=stamp(),context='Public Moscow destination, RUB, no wallet or personalized account',products=products)
    except Exception as e:errors.append(type(e).__name__)
   return dict(status='unavailable',errors=errors,observed_at=stamp())
  stage('buyer_prices',buyer)
  def week():
   from analytics.mpstats_probe import discover
   from analytics.mpstats_gaps import execute_reads
   obs=[];first,last='2026-11-07','2026-11-09'
   tasks=[dict(cabinet='token_3',tool='lk_wb_products',key='owner-audit17-week',priority=80,arguments=dict(date_from=first,date_to=last,start_row=0,end_row=1000))]
   def persist(cabinet,row):
    if cabinet=='token_3'and row.get('scope_verified')is True and row.get('status')=='received':obs.append(row)
   def extra(call,checks,known):return execute_reads(call,checks,known,tasks,{},persist,max_requests=1)
   discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
   assert len(obs)==1;body=obs[0]['data']['data'];rows=body['data'];assert body['need_update']==0 and body['total']==len(rows)
   fields=('nm_id','sa_name','orders_count','orders_sum','open_card_count','add_to_cart_count','funnel_orders_count','price_after_discount','price_after_spp','price_spp','fbs_stock','days_in_stock')
   return dict(observed_at=stamp(),period_from=first,period_to=last,rows=[{k:r.get(k)for k in fields}for r in rows],source='MPStats all-source, RUB')
  stage('week_funnel',week)
  arts=set(scope['stock_articles']);ledger=scope['ledger'];tokens=[os.environ['WB_TOKEN_'+str(i)]for i in(1,2,3)]
  def poolstocks():
   out={}
   for part in scope['pool_cards']:
    i=part['cabinet']
    if i==3:continue
    mp={s['chrtID']:r['vendorCode'].casefold()for r in part['cards']for s in r.get('sizes',[])}
    raw=req('marketplace-api.wildberries.ru','/api/v3/stocks/'+str(WAREHOUSES[i]),dict(chrtIds=sorted(mp)),index=i)['stocks']
    assert {r['chrtId']for r in raw}==set(mp)
    out[str(i)]=dict(observed_at=stamp(),amounts={a:sum(r['amount']for r in raw if mp[r['chrtId']]==a)for a in set(mp.values())})
   return out
  stage('pool_stocks',poolstocks)
  def orderunits():
   out=[];end=datetime.now(timezone.utc);baseline=datetime.fromtimestamp(ledger['source_observed_at'],timezone.utc)-timedelta(seconds=5)
   for i in range(3):
    old=[u for u in ledger['open_units']if u['cabinet']==i];first=min([baseline]+[datetime.fromisoformat(u['created_at'].replace('Z','+00:00'))-timedelta(seconds=1)for u in old]);cursor=0;found={}
    for _ in range(12):
     j=req('marketplace-api.wildberries.ru','/api/v3/orders',params=dict(limit=1000,next=cursor,dateFrom=int(first.timestamp()),dateTo=int(end.timestamp())),index=i)
     rows=j['orders']
     for r in rows:
      if str(r.get('article','')).casefold()in arts and r.get('warehouseId')==WAREHOUSES[i]:found[r['id']]=r
     if not rows or not j.get('next'):break
     assert j['next']!=cursor;cursor=j['next']
    else:raise ValueError('Bounded order discovery incomplete')
    for r in req('marketplace-api.wildberries.ru','/api/v3/orders/new',index=i)['orders']:
     if str(r.get('article','')).casefold()in arts and r.get('warehouseId')==WAREHOUSES[i]:found[r['id']]=r
    ids=sorted(set(found)|{int(u['id'])for u in old});statuses={}
    for k in range(0,len(ids),1000):statuses.update({s['id']:s for s in req('marketplace-api.wildberries.ru','/api/v3/orders/status',dict(orders=ids[k:k+1000]),index=i)['orders']})
    assert set(statuses)==set(ids);oldmap={int(u['id']):u for u in old}
    for ident in ids:
     s=statuses[ident];seller=s['supplierStatus'];ws=s['wbStatus'];assert seller in('new','confirm','complete','cancel','cancel_carrier')
     r=found.get(ident);u=dict(cabinet=i,id=str(ident),article=r['article'].casefold(),group='wb:'+str(r['supplyId'])if r.get('supplyId')else'wb:'+str(i)+':order:'+str(ident),quantity=1,fulfillment='fbs',created_at=r['createdAt'])if r else copy.deepcopy(oldmap[ident])
     u.update(supplier_status=seller,wb_status=ws,cancelled_before_ship=seller=='cancel'or(seller in('new','confirm')and ws in('declined_by_client','canceled')));out.append(u)
   return dict(observed_at=stamp(),units=out)
  stage('pool_orders_wb',orderunits)
  def oz(path,body):
   r=requests.post(os.environ['SUPABASE_URL'].rstrip('/')+'/functions/v1/stock-ozon-read',headers={'x-stock-backend-key':os.environ['SUPABASE_SECRET_KEY']},json=dict(path=path,body=body),timeout=(10,50));r.raise_for_status();j=r.json();assert j['upstream_status']==200;return j['data']
  def ozon():
   start=ledger['source_observed_at']-5;old=[u for u in ledger['open_units']if u['cabinet']==3]
   if old:start=min([start]+[datetime.fromisoformat(u['created_at'].replace('Z','+00:00')).timestamp()-86400 for u in old])
   cursor='';units=[]
   for _ in range(12):
    j=oz('/v4/posting/fbs/list',dict(dir='ASC',filter={'since':datetime.fromtimestamp(start,timezone.utc).isoformat(),'to':stamp()},limit=100,cursor=cursor,**{'with':{'analytics_data':False,'financial_data':False}}));posts=j['postings']
    for r in posts:
     for p in r['products']:
      a=p['offer_id'].casefold()
      if a in arts:
       assert not r.get('parent_posting_number'),'Split requires exact reconciliation'
       units.append(dict(cabinet=3,id=r['posting_number'],article=a,group='ozon:'+r['posting_number'],quantity=p['quantity'],fulfillment='fbs',status=r['status'],created_at=r.get('in_process_at'),cancelled_before_ship=r['status']in('canceled','cancelled')and r.get('cancellation',{}).get('cancelled_after_ship')is False))
    if j['has_next']is False:break
    assert j.get('cursor')and j['cursor']!=cursor;cursor=j['cursor']
   else:raise ValueError('Ozon discovery incomplete')
   assert {u['id']for u in old}<={u['id']for u in units}
   cards=next((x['cards']for x in scope['pool_cards']if x['cabinet']==3),[]);offers=[x['_ozon_offer_id']for x in cards]
   stocks=oz('/v2/product/info/stocks-by-warehouse/fbs',dict(offer_id=offers,limit=1000,cursor=''))if offers else{}
   return dict(observed_at=stamp(),units=units,stock=stocks)
  stage('pool_ozon',ozon)
  def reconcile_pool():
   from stock_current_order_reserve import identity,select_current,group_context,reconcile_current
   merged={identity(u):u for u in ledger['order_catalog']};merged.update({identity(u):u for u in v['pool_orders_wb']['units']+v['pool_ozon']['units']});allunits=list(merged.values());units=select_current(allunits,ledger);groups={u['group']for u in units};numbers={u['id']for u in units if u['cabinet']==3}
   headers={};since=datetime.fromtimestamp(ledger['ms_scan_from']-5,timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M:%S')
   def ms(path,params=None):
    r=requests.get(BASE+path,headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip'},params=params,timeout=(10,45));r.raise_for_status();return r.json()
   for off in range(0,10000,100):
    j=ms('/entity/demand',dict(filter='store='+BASE+'/entity/store/'+STORE+';updated>='+since,limit=100,offset=off,expand='positions'));rows=j['rows']
    for d in rows:headers[d['id']]=d
    if off+len(rows)==j['meta']['size']:break
    assert rows
   else:raise ValueError('Demand pagination incomplete')
   docs={d['id']:d for d in ledger['documents']};orders={}
   for d in headers.values():
    ref=d.get('customerOrder',{}).get('meta',{}).get('href');o={}
    if ref:
     if ref not in orders:orders[ref]=ms(ref.removeprefix(BASE))
     o=orders[ref]
    text=' '.join(str(x or'')for x in(d.get('externalCode'),d.get('description'),o.get('name'),o.get('description')));wb=set(re.findall(r'WB-GI-\d+',text));ozids=set(re.findall(r'(?<![\w-])\d{5,}-\d{3,}-\d+(?![\w-])',text));group='wb:'+next(iter(wb))if len(wb)==1 else'ozon:'+next(iter(ozids))if len(ozids)==1 else None
    if group not in groups and not ozids&numbers:continue
    assert len(wb)<=1 and len(ozids)<=1,'Ambiguous document identity'
    pos=d.get('positions',{});parts=pos.get('rows')
    if not isinstance(parts,list)or len(parts)!=pos['meta']['size']:
     parts=[]
     for off in range(0,10000,1000):
      j=ms('/entity/demand/'+d['id']+'/positions',dict(limit=1000,offset=off));parts+=j['rows']
      if len(parts)==j['meta']['size']:break
     assert len(parts)==j['meta']['size']
    counts=Counter()
    for x in parts:
     a=reader.products.get(x.get('assortment',{}).get('meta',{}).get('href','').split('?')[0])
     if a in arts:counts[a]+=x['quantity']
    docs[d['id']]=dict(id=d['id'],group=group,applicable=d.get('applicable')is True,store_id=STORE,quantities=dict(counts),updated=d['updated'])
   fresh=reader.stock([x['article']for x in scope['catalog']if x['article'].casefold()in arts],'msk');assert fresh['coverage_complete']
   physical={r['article'].casefold():r['stock']-r['reserve']for r in fresh['rows']};result=reconcile_current(physical,units,list(docs.values()),STORE,group_context(allunits))
   return dict(result,observed_at=stamp(),physical_observed_at=fresh['observed_at'],source_ledger_observed_at=ledger['source_observed_at'],wb_writes=0)
  stage('pool_reconciliation',reconcile_pool)
  v.update(status='complete'if not v['errors']else'partial',completed_at=stamp());c.put(ROOT+':fresh',v)
  print(json.dumps(dict(status=v['status'],errors=v['errors'],wb_writes=0,telegram_calls=0,model_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
