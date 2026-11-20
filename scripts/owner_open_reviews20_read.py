"""Read-only evidence for owner-requested sequential test review."""
import requests,json,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:open_reviews20:v1'
def main():
 io=AdvertisingIO();ids=io.get(ROOT+':scope')['nm_ids'];assert len(ids)<=15
 out=dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,errors={});assert io.create(ROOT,out)
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or '';p=u.path
  assert 'telegram'not in host and 'openai'not in host
  if host.endswith('wildberries.ru'):
   assert m=='GET'and p=='/api/v2/list/goods/filter'or m=='POST'and p in('/api/v3/stocks/2126188','/api/analytics/v3/sales-funnel/products')
  if host.endswith('moysklad.ru'):assert m=='GET'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def save():io.put(ROOT,copy.deepcopy(out))
 def read(name,fn):
  try:out[name]=fn()
  except Exception as e:out['errors'][name]=str(e)[:250]
  save()
 read('prices',lambda:current_prices(io,ids))
 if out.get('prices'):
  read('published_stock',lambda:published_stock(io,out['prices'],ids))
  read('stock',lambda:read_stock([r['article']for r in out['prices']['rows']]))
 if out.get('stock'):
  base=io.get('china_agent:advertising_full_growth:2026-11-20:v1:inputs')
  read('economics',lambda:model_rows(dict(products=base['own'],prices=out['prices'],stock=out['stock'],fx=base['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1')))
 def funnel():
  nms=[r['nm_id']for r in out['prices']['rows']if 'furcoat'in r['article']]
  body=dict(selectedPeriod=dict(start='2026-11-19',end='2026-11-19'),pastPeriod=dict(start='2026-11-17',end='2026-11-17'),nmIds=nms,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy=dict(field='openCard',mode='desc'),limit=100,offset=0)
  r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token},json=body,timeout=50);r.raise_for_status()
  return dict(request=body,response=r.json(),observed_at=datetime.now(timezone.utc).isoformat())
 read('fur_funnel',funnel)
 out.update(status='complete'if not out['errors']else'partial',completed_at=datetime.now(timezone.utc).isoformat());save()
 print(json.dumps(dict(status=out['status'],errors=out['errors'])))
if __name__=='__main__':main()
