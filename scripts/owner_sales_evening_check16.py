"""No repeated order/stat collection: exact saved order statuses and three stock gaps, read only."""
import os,json
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
ROOT='china_agent:owner_sales_urgent:2026-11-16:evening:v1'
KEY=ROOT+':focused_check'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();source=c.get(ROOT);assert source['status']=='complete'
 if not c.create(KEY+':claim',dict(at=stamp(),wb_writes=0)):raise RuntimeError('Already claimed; inspect saved result')
 out=dict(status='collecting',observed_at=stamp(),source_key=ROOT,errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 def read(k,fn):
  try:out[k]=fn()
  except Exception as e:out['errors'][k]=type(e).__name__+': '+str(e)[:200]
  c.put(KEY,out)
 ids=[r['id']for r in source['orders']['periods']['0']['rows']];assert 0<len(ids)<=100
 def states():
  r=requests.post('https://marketplace-api.wildberries.ru/api/v3/orders/status',headers={'Authorization':os.environ['WB_TOKEN_3']},json={'orders':ids},timeout=(10,45));r.raise_for_status();body=r.json();assert {r['id']for r in body['orders']}==set(ids);return body
 read('order_statuses',states)
 def order_statistics():
  r=requests.get('https://statistics-api.wildberries.ru/api/v1/supplier/orders',params={'dateFrom':'2026-11-16','flag':1},headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(10,60));r.raise_for_status();rows=r.json();assert isinstance(rows,list)and len(rows)<80000
  fields=('date','lastChangeDate','supplierArticle','nmId','srid','warehouseName','orderType','isCancel','cancelDate','totalPrice','discountPercent','spp','priceWithDisc','finishedPrice')
  recent=[{k:x.get(k)for k in fields}for x in rows if str(x.get('date','')).startswith('2026-11-16')and str(x['date'])[11:13]>='19']
  return dict(observed_at=stamp(),source='statistics_orders_api',all_today_rows=len(rows),rows19=recent,latest_date=max((str(x.get('date',''))for x in rows),default=None),money_currency='not_declared_by_endpoint_not_assumed_CNY')
 read('order_statistics',order_statistics)
 class Prices:
  token=os.environ['WB_TOKEN_3']
  def wb(self,path):
   r=requests.get('https://discounts-prices-api.wildberries.ru'+path,headers={'Authorization':self.token},timeout=(10,45));r.raise_for_status();return r.json()['data']
 io=Prices();nms=[1560345288,1560345289,1560345287]
 read('prices',lambda:current_prices(io,nms))
 if 'prices'in out:
  read('stock',lambda:read_stock([r['article']for r in out['prices']['rows']]))
  read('published_stock',lambda:published_stock(io,out['prices'],nms))
 out.update(status='complete'if not out['errors']else'partial',completed_at=stamp());c.put(KEY,out)
 print(json.dumps(dict(status=out['status'],errors=out['errors'],wb_writes=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':
 old=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=method=='POST'and u.path in('/api/v3/orders/status','/api/v3/stocks/2126188')
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=method=='GET'and u.path=='/api/v2/list/goods/filter'
  elif u.hostname=='statistics-api.wildberries.ru':ok=method=='GET'and u.path=='/api/v1/supplier/orders'
  elif u.hostname=='api.moysklad.ru':ok=method=='GET'and u.path.startswith('/api/remap/1.2/')
  else:ok=False
  assert ok,'Read-only followup scope rejected'
  return old(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=old

