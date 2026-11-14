"""Owner-requested scoped campaign diagnosis. No marketplace writes or Telegram/model calls."""
import os,json
from datetime import datetime,timezone,date,timedelta
from urllib.parse import urlparse,urlencode
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http,save
ROOT='china_agent:owner_363_review:2026-11-15:v1'
def main():
 io=AdvertisingIO()
 import requests
 original=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  p=urlparse(url);m=method.upper()
  if 'openai' in p.hostname or p.hostname=='api.telegram.org':raise ValueError('No model or Telegram calls')
  if p.hostname and p.hostname.endswith('wildberries.ru'):
   allow=(m=='GET' and p.path in ['/api/advert/v2/adverts','/adv/v3/fullstats','/api/advert/v1/config','/api/v2/list/goods/filter']) or (m=='POST' and p.path in ['/api/advert/v2/budget','/api/advert/v1/bids/min','/api/v3/stocks/2126188'])
   if not allow:raise ValueError('Marketplace mutation prohibited')
  return original(session,method,url,**kw)
 requests.sessions.Session.request=guard
 v=io.get(ROOT)or dict(status='collecting',cabinet='token_3',wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 def checkpoint():save(io,ROOT,json.loads(json.dumps(v)))
 try:
  if v.get('status')=='complete':return
  if 'campaign'not in v:v['campaign']=http(io,'/api/advert/v2/adverts?ids=41296363')['adverts'][0];checkpoint()
  if 'budget'not in v:v['budget']=http(io,'/api/advert/v2/budget','POST',dict(advertIds=[41296363]));checkpoint()
  if 'stats'not in v:v['stats']=http(io,'/adv/v3/fullstats?ids=41296363&beginDate=2026-11-10&endDate=2026-11-14');checkpoint()
  raw=v['stats'][0];members={n['nm_id']for n in v['campaign']['nm_settings']}
  associated={r['nmId']for d in raw.get('days',[])for a in d.get('apps',[])for r in a.get('nms',[])if r.get('orders',0)>0}
  ids=sorted(members|associated)
  from china_morning_readiness import current_prices,published_stock
  if 'prices'not in v:
   # Some associated items are outside our seller catalogue. Discover once, retain this fact.
   goods=io.wb('/api/v2/list/goods/filter?limit=1000&offset=0').get('listGoods')
   assert isinstance(goods,list)and len(goods)<1000,'Price pagination scope exceeded'
   found={g['nmID']:g for g in goods if g['nmID']in ids};rows=[]
   for nm,g in found.items():
    vals={z.get('discountedPrice')for z in g['sizes']}
    assert g['currencyIsoCode4217']=='CNY'and len(vals)==1
    rows.append(dict(nm_id=nm,article=g['vendorCode'],seller_price=next(iter(vals)),currency='CNY',size_ids=[z['sizeID']for z in g['sizes']]))
   assert members<=set(found),'Current member price missing'
   v['prices']=dict(rows=rows,observed_at=datetime.now(timezone.utc).isoformat())
   v['associated_not_seller_catalogue']=sorted(associated-set(found));checkpoint()
  ids=[r['nm_id']for r in v['prices']['rows']]
  if 'published_stock'not in v:v['published_stock']=published_stock(io,v['prices'],ids);checkpoint()
  from china_moysklad_read import read_stock
  if 'stock'not in v:v['stock']=read_stock([r['article']for r in v['prices']['rows']]);checkpoint()
  class Work:
   now=datetime.now(timezone.utc)
   def get(self,k):return io.get(k)
   def save(self,k,value,**kw):save(io,k,value)
   def db(self,method,table,params=None):
    assert method=='GET'and table=='analytics_snapshots'
    return io.db(table+'?'+urlencode(params or{}))
   def catalog(self):return[(str(r['nm_id']),r['article'])for r in v['prices']['rows']]
  from china_analytic_dialog import Analyst,reading
  if 'own'not in v:
   with reading():v['own']=Analyst(Work(),dict(request_text='Экономика РК41296363, только чтение'),[]).live('products',[],'2026-10-16','2026-11-14')
   v['own'].update(period_from='2026-10-16',period_to='2026-11-14');checkpoint()
  from china_intraday_analysis import rate
  if 'fx'not in v:v['fx']=rate(Work(),date(2026,11,15));checkpoint()
  if 'economics'not in v:
   from china_advertising_economic_review import model_rows
   v['economics']=model_rows(dict(products=v['own'],prices=v['prices'],stock=v['stock'],fx=v['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
   for nm,e in v['economics']['rows'].items():e.update(fx_rub_per_cny=float(v['fx']['rub_per_cny']),published_stock=v['published_stock']['amounts'].get(nm),published_stock_observed_at=v['published_stock']['observed_at'])
   checkpoint()
  if 'minimums'not in v:v['minimums']=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=41296363,nm_ids=sorted(members),payment_type='cpc',placement_types=['recommendation']));checkpoint()
  v.update(status='complete',observed_at=datetime.now(timezone.utc).isoformat());checkpoint()
  print(json.dumps(dict(status=v['status'],members=len(members),models=len(v['economics']['rows']),missing=v['economics']['missing'],associated_not_seller_catalogue=v['associated_not_seller_catalogue']),ensure_ascii=False))
 except Exception as e:
  v.update(status='collecting',error=type(e).__name__+': '+str(e),last_attempt_at=datetime.now(timezone.utc).isoformat());checkpoint();raise
if __name__=='__main__':main()
