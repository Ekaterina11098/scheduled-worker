import os,json,requests,time
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_noel0_596_price_review:2026-11-24:v1'
IDS=[1473243891,1473243900]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':return
 if not v:v=dict(status='reading',errors={},wb_writes=0,telegram_calls=0,model_calls=0,observed_at=now());assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='POST'and u.path=='/api/analytics/v3/sales-funnel/products'and (kw.get('json')or{}).get('nmIds')==IDS)
  assert ok,'Two SKU read only';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 if 'prices'not in v:
  goods=io.wb('/api/v2/list/goods/filter?limit=1000&offset=0')['listGoods'];assert len(goods)<1000
  v['prices']=[p for p in goods if p['nmID']in IDS];assert len(v['prices'])==2 and all(p['currencyIsoCode4217']=='CNY'for p in v['prices']);v['price_observed_at']=now();io.put(ROOT,v)
 if 'funnel'not in v:
  body=dict(selectedPeriod={'start':'2026-11-20','end':'2026-11-23'},pastPeriod={'start':'2026-11-12','end':'2026-11-15'},nmIds=IDS,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
  r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token},json=body,timeout=(10,55));r.raise_for_status()
  v['funnel']=dict(request=body,response=r.json(),observed_at=now());assert {p['product']['nmId']for p in v['funnel']['response']['data']['products']}==set(IDS);io.put(ROOT,v)
 v.update(status='complete',completed_at=now());io.put(ROOT,v);print(json.dumps({'status':v['status'],'wb_writes':0}))
if __name__=='__main__':main()
