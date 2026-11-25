"""Bounded owner-requested sales leader diagnosis. Read-only, checkpoints, no Telegram/model."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse,urlencode
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import Reader
from china_advertising_economic_review import model_rows
from china_wb_evidence import Reports,FUNNEL,normalize_funnel
ROOT='china_agent:owner_catalog25_actions26:v2'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();cat=io.get('china_agent:prices:v1');assert cat['cabinet']=='token_3';IDS=sorted(r['nmID']for r in cat['rows'])
 if io.get(ROOT):print('Existing checkpoint retained; do not repeat');return
 validate_identity(Cache(),WB());out=dict(status='reading',started_at=stamp(),nm_ids=IDS,errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,out)
 def save():io.put(ROOT,json.loads(json.dumps(out)))
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();p=u.path
  ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and p.startswith('/rest/v1/')
  if u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/');time.sleep(.55)
  if u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and p=='/api/v2/list/goods/filter'
  if u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p=='/api/v3/stocks/2126188'
  if u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='POST'and p=='/api/analytics/v3/sales-funnel/products'
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config')or m=='POST'and p=='/api/advert/v1/bids/min'
  if u.hostname=='card.wb.ru':ok=m=='GET'and p in('/cards/v4/detail','/cards/v2/detail')
  if u.hostname=='dp-calendar-api.wildberries.ru':ok=m=='GET'and p in('/api/v1/calendar/promotions','/api/v1/calendar/promotions/nomenclatures')
  if u.hostname=='mcp.mpstats.io':
   b=kw.get('json')or{};name=(b.get('params')or{}).get('name');ok=m=='POST'and p=='/mcp'and(b.get('method')in('initialize','notifications/initialized','tools/list')or b.get('method')=='tools/call'and name in('account_limits','lk_wb_cabinets','lk_wb_products'))
  assert ok,'Read-only owner diagnosis scope '+m+' '+str(u.hostname)+p
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def get(host,path,params=None,body=None,auth=True):
  time.sleep(1);r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers={'Authorization':io.token}if auth else{},timeout=(8,45))
  if not r.ok:raise ValueError('HTTP '+str(r.status_code)+' '+host+path)
  return r.json()
 def stage(k,fn):
  try:out[k]=fn()
  except Exception as ex:out['errors'][k]=type(ex).__name__+': '+str(ex)[:220]
  save()
 class Adapter:
  def get(self,k):return io.get(k)
  def save(self,k,v):return io.put(k,v)if io.get(k)is not None else io.create(k,v)
  def db(self,method,table,params=None,body=None,prefer=None):
   assert table=='telegram_api_cache';return io.db(table+'?'+urlencode(params or{}),method,body,prefer)
 try:
  def funnel():
   selected=dict(start='2026-11-12',end='2026-11-25');past=dict(start='2026-10-29',end='2026-11-11')
   body=dict(selectedPeriod=selected,pastPeriod=past,nmIds=[],brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy=dict(field='openCard',mode='desc'),limit=1000,offset=0)
   r=Reports(Adapter()).request(FUNNEL,body)
   if not r['available']:return dict(status='unavailable',reason=r.get('status'),retry_at=r.get('retry_at'))
   d=r['data']['data'];assert d['currency']=='CNY'and isinstance(d['products'],list)and len(d['products'])<1000
   rows=normalize_funnel(d['products'],selected,past,ROOT+':funnel')
   return dict(status='complete',observed_at=r['observed_at'],rows=rows,scope='all_sources',past_is_full_day=True,update_delay_hours=2)
  out['funnel']=io.get('china_agent:owner_catalog25_actions26:v1')['funnel'];save()
  def tolerant_prices():
   raw=get('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',dict(limit=1000,offset=0));goods=raw['data']['listGoods']if 'data'in raw else raw['listGoods'];assert len(goods)<1000
   mapping={g['nmID']:g for g in goods};rows=[];missing=[]
   for nm in IDS:
    g=mapping.get(nm)
    if not g or g.get('currencyIsoCode4217')!='CNY':missing.append(dict(nm_id=nm,reason='missing_or_currency'));continue
    vals={float(z['discountedPrice'])for z in g.get('sizes',[])}
    if len(vals)!=1:missing.append(dict(nm_id=nm,reason='size_prices_ambiguous'));continue
    rows.append(dict(nm_id=nm,article=g['vendorCode'],currency='CNY',size_ids=[z['sizeID']for z in g['sizes']],seller_price=vals.pop()))
   return dict(rows=rows,raw_goods=[g for g in goods if g['nmID']in IDS],missing=missing,observed_at=stamp())
  stage('prices',tolerant_prices)
  if 'prices'in out:
   class MemoReader(Reader):
    memo={}
    def pages(self,path,params):
     key=(path,json.dumps(params,sort_keys=True))
     if path in('/entity/product','/entity/store')and key in self.memo:return self.memo[key]
     rows=super().pages(path,params)
     if path in('/entity/product','/entity/store'):self.memo[key]=rows
     return rows
   reader=MemoReader();articles=[r['vendorCode']for r in cat['rows']]
   stage('stock',lambda:reader.stock(articles,'msk'))
   stage('stock_guangzhou',lambda:reader.stock(articles,'guangzhou'))
   stage('published',lambda:published_stock(io,out['prices'],[r['nm_id']for r in out['prices']['rows']]))
  if 'stock'in out:
   def economy():
    source=io.get('china_agent:advertising_full_growth:2026-11-25:v1:inputs:midday');assert source['status']=='complete'
    return model_rows(dict(products=source['own'],prices=out['prices'],stock=out['stock'],fx=source['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
   stage('economics',economy)
  def public():
   params=dict(appType=1,curr='rub',dest=-1257786,spp=30,nm=';'.join(map(str,IDS)));errors=[]
   for v in (4,2):
    try:
     j=get('card.wb.ru','/cards/v'+str(v)+'/detail',params,auth=False);r=j.get('products',j.get('data',{}).get('products'));assert isinstance(r,list)
     return dict(observed_at=stamp(),context='Moscow,RUB,unauthenticated,no wallet/personal discount',version=v,rows=[{k:p.get(k)for k in('id','name','sizes','sale','salePriceU','priceU','promotions','promoTextCard','totalQuantity','rating','reviewRating','feedbacks')}for p in r],missing=sorted(set(IDS)-{p['id']for p in r}))
    except Exception as ex:errors.append(type(ex).__name__+': '+str(ex)[:100])
   raise ValueError(';'.join(errors))
  # Not repeating blocked public buyer-price API
  if False: # Known stale connected-cabinet price snapshots not used for live buyer prices
   def mp():
    from analytics.mpstats_probe import discover
    from analytics.mpstats_gaps import execute_reads
    observations=[];tasks=[dict(cabinet='token_3',tool='lk_wb_products',key='owner-leaders25:2026-11-25',priority=80,arguments=dict(date_from='2026-11-25',date_to='2026-11-25',start_row=0,end_row=1000))]
    def persist(cabinet,obs):
     if cabinet=='token_3'and obs.get('scope_verified')is True and obs.get('status')=='received':observations.append(obs)
    def extra(call,checks,known):return execute_reads(call,checks,known,tasks,{},persist,max_requests=1)
    discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra);assert len(observations)==1
    body=observations[0]['data']['data'];rows=body['data'];assert body.get('need_update')==0 and body.get('total')==len(rows)
    selected=[r for r in rows if int(r['nm_id'])in IDS]
    return dict(observed_at=stamp(),source='MPStats WB connected cabinet',rows=selected,missing=sorted(set(IDS)-{int(r['nm_id'])for r in selected}),need_update=body.get('need_update'),not_direct_WB_live=True)
   stage('buyer_mpstats',mp)
  def promos():
   j=get('dp-calendar-api.wildberries.ru','/api/v1/calendar/promotions',dict(startDateTime='2026-11-25T00:00:00Z',endDateTime='2026-11-25T23:59:59Z',allPromo='false'));p=j.get('data',{}).get('promotions');assert isinstance(p,list)
   result=dict(observed_at=stamp(),promotions=p,rows=[],unavailable=[],coverage_complete=len(p)<=10)
   for x in p[:10]:
    try:
     z=get('dp-calendar-api.wildberries.ru','/api/v1/calendar/promotions/nomenclatures',dict(promotionID=x['id'],inAction='true',limit=1000,offset=0));r=z['data']['nomenclatures'];assert isinstance(r,list)and len(r)<1000
     result['rows'] +=[dict(promotion_id=x['id'],promotion_name=x.get('name'),row=n)for n in r if int(n.get('id',n.get('nmID',n.get('nm_id',0))))in IDS]
    except Exception as ex:result['unavailable'].append(dict(id=x['id'],reason=type(ex).__name__));result['coverage_complete']=False
   return result
  # No broad promo retries
  latest=io.get('china_agent:hourly_sales_api:v1:snapshot:2026-11-25T23:MSK');assert latest
  out['campaigns']=latest['advertising']['campaigns'];out['campaign_snapshot_key']='china_agent:hourly_sales_api:v1:snapshot:2026-11-25T23:MSK';save()
  out.update(status='complete_with_gaps'if out['errors']else'complete',completed_at=stamp());save();print(json.dumps(dict(status=out['status'],errors=out['errors'],wb_writes=0,telegram_calls=0,model_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
