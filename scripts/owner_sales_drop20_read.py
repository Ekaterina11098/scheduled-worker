"""Bounded read-only sales drop diagnosis, commercial scope private."""
import requests,os,json,time
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_hourly_sales_read import read_orders,select_rows,aggregate
from china_morning_readiness import current_prices,published_stock
from china_advertising_v2 import http
ROOT='china_agent:sales_drop20:v1'
def main():
 io=AdvertisingIO();spec=io.get(ROOT+':request');out=dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,orders={});assert io.create(ROOT,out)
 def save():io.put(ROOT,out)
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  host=urlparse(url).hostname or '';path=urlparse(url).path;m=method.upper()
  assert 'telegram'not in host and 'openai'not in host
  if host.endswith('wildberries.ru'):
   assert m=='GET'and path in('/api/v3/orders','/api/v3/orders/new','/api/v2/list/goods/filter','/api/advert/v2/adverts','/adv/v1/promotion/count')or m=='POST'and path in('/api/v3/stocks/2126188','/api/v3/orders/status','/api/advert/v2/budget')
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def get(path,params=None):
  r=requests.get('https://marketplace-api.wildberries.ru'+path,headers={'Authorization':io.token},params=params,timeout=45);r.raise_for_status();return r.json()
 try:
  cut=datetime.now(ZoneInfo('Europe/Moscow')).replace(microsecond=0);out['cut_msk']=cut.isoformat()
  fresh=get('/api/v3/orders/new')['orders'];save()
  for off in(0,1,7):
   end=cut-timedelta(days=off);start=end.replace(hour=0,minute=0,second=0)
   raw=read_orders(get,start,end)
   for r in fresh:raw[r['id']]=r
   rows=select_rows(raw.values(),start,end);out['orders'][str(off)]=dict(rows=rows,totals=aggregate(rows),start=start.isoformat(),end=end.isoformat(),observed_at=datetime.now(timezone.utc).isoformat());save()
  out['prices']=current_prices(io,spec['nm_ids']);save()
  out['published_stock']=published_stock(io,out['prices'],spec['nm_ids']);save()
  counts=http(io,'/adv/v1/promotion/count');ids=sorted({a['advertId']for g in counts.get('adverts',[])if g['status']in(9,11)for a in g.get('advert_list',[])})
  out['campaigns']=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts'];save()
  out['budgets']=http(io,'/api/advert/v2/budget','POST',dict(advertIds=ids));save()
  out.update(status='complete',completed_at=datetime.now(timezone.utc).isoformat());save()
 except Exception as ex:out.update(status='blocked',error=str(ex)[:300]);save();raise
 print(json.dumps(dict(status=out['status'],wb_writes=0)))
if __name__=='__main__':main()
