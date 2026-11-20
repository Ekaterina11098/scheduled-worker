"""Owner-requested full assortment evidence. Read-only WB/MSK; no Telegram/model."""
import copy,json,requests
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from china_morning_readiness import published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:extra_advertising:2026-11-20:v1'
def main():
 io=AdvertisingIO();v=io.get(ROOT)or dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,created_at=datetime.now(timezone.utc).isoformat())
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or''
  if host=='api.telegram.org'or'openai'in host:raise ValueError('No Telegram or model')
  if host.endswith('wildberries.ru'):
   allowed=m=='GET'and u.path in('/api/v2/list/goods/filter','/adv/v1/promotion/count','/api/advert/v2/adverts','/api/advert/v1/config')or m=='POST'and u.path in('/api/advert/v1/bids/min','/api/v3/stocks/2126188')
   assert allowed,'Marketplace mutation/unscoped endpoint prohibited'
  if host.endswith('moysklad.ru'):assert m=='GET','No stock changes'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def save():
  v['updated_at']=datetime.now(timezone.utc).isoformat()
  if io.get(ROOT)is None:assert io.create(ROOT,v)
  else:io.put(ROOT,copy.deepcopy(v))
 old=io.get('china_agent:advertising_full_growth:2026-11-20:v1:inputs');assert old['status']=='complete'
 if 'goods'not in v:
  goods=[]
  for offset in range(0,20000,1000):
   part=io.wb('/api/v2/list/goods/filter?limit=1000&offset='+str(offset))['listGoods'];goods+=part
   if len(part)<1000:break
  else:raise ValueError('Catalogue pagination bound')
  rows=[];bad={}
  for g in goods:
   vals={s.get('discountedPrice')for s in g['sizes']}
   if len(vals)!=1 or g.get('currencyIsoCode4217')!='CNY'or not next(iter(vals),0):bad[str(g['nmID'])]='Exact CNY price missing';continue
   rows.append(dict(nm_id=g['nmID'],article=g['vendorCode'],seller_price=next(iter(vals)),size_ids=[s['sizeID']for s in g['sizes']]))
  v['prices']=dict(rows=rows,observed_at=datetime.now(timezone.utc).isoformat(),missing=bad)
  v['goods']=dict(nm_ids=[g['nmID']for g in goods],count=len(goods),catalogue_missing_nm_ids=sorted({r['nmID']for r in old['catalogue']['rows']}-{g['nmID']for g in goods}));save()
 if 'stock'not in v:
  articles=sorted({r['vendorCode']for r in old['catalogue']['rows']}|{r['article']for r in v['prices']['rows']})
  v['stock']=read_stock(articles);save()
 if 'published_stock'not in v:
  v['published_stock']=published_stock(io,v['prices'],[r['nm_id']for r in v['prices']['rows']]);save()
 if 'campaigns'not in v:
  inventory=http(io,'/adv/v1/promotion/count');ids=sorted({a['advertId']for t in inventory.get('adverts',[])if t.get('status')in(9,11)for a in t.get('advert_list',[])})
  campaigns=[]
  for start in range(0,len(ids),50):campaigns+=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,ids[start:start+50])))['adverts']
  v['campaigns']=campaigns;v['campaigns_observed_at']=datetime.now(timezone.utc).isoformat();save()
 if 'economics'not in v:
  policy=io.get('china_agent:new_ad_economics_policy:v1');delivery=io.get('china_agent:expected_profit_delivery_model:v1')
  inputs=dict(products=old['own'],prices=v['prices'],stock=v['stock'],fx=old['fx'])
  v['economics']=model_rows(inputs,policy,delivery)
  for nm,e in v['economics']['rows'].items():e.update(published_stock=v['published_stock']['amounts'].get(nm),published_stock_observed_at=v['published_stock']['observed_at'])
  v['economic_policy']=dict(planned_buyout_by_nm=policy.get('planned_buyout_by_nm',{}),category_minimum_minor=policy.get('category_minimum_minor',{}));save()
 if 'category_quotes'not in v:
  quotes={}
  for c in v['campaigns']:
   if c.get('bid_type')!='manual'or c['settings']['payment_type']!='cpc':continue
   for n in c['nm_settings']:
    subject=n['subject']['id']
    for zone in ['search','recommendations']:
     k=str(subject)+':'+zone
     if k in quotes or not c['settings']['placements'].get(zone):continue
     z='search'if zone=='search'else'recommendation'
     q=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=c['id'],nm_ids=[n['nm_id']],payment_type='cpc',placement_types=[z]))
     quotes[k]=dict(campaign_id=c['id'],nm_id=n['nm_id'],subject_id=subject,placement=zone,response=q,observed_at=datetime.now(timezone.utc).isoformat())
  v['category_quotes']=quotes;save()
 v.update(status='complete',completed_at=datetime.now(timezone.utc).isoformat(),source_own_period=[old['own']['period_from'],old['own']['period_to']],source_own_snapshot=old['own'].get('snapshot_id'));save()
 print(json.dumps(dict(status=v['status'],goods=v['goods']['count'],stock_rows=len(v['stock']['rows']),models=len(v['economics']['rows']),quote_groups=len(v['category_quotes']),wb_writes=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':main()

