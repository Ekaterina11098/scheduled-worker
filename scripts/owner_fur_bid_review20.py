"""Bounded owner-requested read-only review; private scope; no TG/model."""
import requests,json,time
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:fur_bid_review:2026-11-20:v1'
def main():
 io=AdvertisingIO();spec=io.get(ROOT+':request');ids=spec['nm_ids'];cid=spec['campaign_id']
 out=dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,started_at=datetime.now(timezone.utc).isoformat())
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  host=urlparse(url).hostname or '';path=urlparse(url).path
  assert 'telegram'not in host and 'openai'not in host
  if host.endswith('wildberries.ru'):
   assert (method.upper()=='GET'and path in('/api/advert/v2/adverts','/api/advert/v1/config','/api/v2/list/goods/filter','/adv/v3/fullstats'))or(method.upper()=='POST'and path in('/api/advert/v1/bids/min','/api/v3/stocks/2126188','/api/advert/v2/budget'))
  if host.endswith('moysklad.ru'):assert method.upper()=='GET'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def save():io.put(ROOT,out)
 try:
  out['campaign']=http(io,'/api/advert/v2/adverts?ids='+str(cid))['adverts'][0];save()
  out['minimum']=http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=ids,payment_type='cpc',placement_types=['recommendation']));save()
  out['prices']=current_prices(io,ids);save()
  out['stock']=read_stock([r['article']for r in out['prices']['rows']]);save()
  out['published_stock']=published_stock(io,out['prices'],ids);save()
  base=io.get('china_agent:advertising_full_growth:2026-11-20:v1:inputs')
  out['economics']=model_rows(dict(products=base['own'],prices=out['prices'],stock=out['stock'],fx=base['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'));save()
  out['budget']=http(io,'/api/advert/v2/budget','POST',dict(advertIds=[cid]));save()
  for day in spec['days']:
   try:out.setdefault('stats',{})[day]=http(io,'/adv/v3/fullstats?ids='+str(cid)+'&beginDate='+day+'&endDate='+day)
   except Exception as e:out.setdefault('stats_errors',{})[day]=str(e)[:250]
   save();time.sleep(21)
  out['status']='complete';out['observed_at']=datetime.now(timezone.utc).isoformat();save()
 except Exception as e:
  out.update(status='blocked',error=str(e)[:500]);save();raise
 print(json.dumps(dict(status=out['status'],wb_writes=0)))
if __name__=='__main__':main()
