"""Owner requested article dashboard details: bounded reads only, no TG."""
import os,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
ROOT='china_agent:sheet_dashboard:v1'
def refresh():
 c=Cache(); original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(c.url).hostname and u.path.startswith('/rest/v1/') and m in ('GET','POST','PATCH')) or (u.hostname=='discounts-prices-api.wildberries.ru' and m=='GET' and u.path=='/api/v2/list/goods/filter') or (u.hostname=='marketplace-api.wildberries.ru' and m=='POST' and u.path=='/api/v3/stocks/2126188' and set((kw.get('json')or{}))=={'chrtIds'})
  assert ok,'Dashboard reads only';return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 try:
  headers={'Authorization':os.environ['WB_TOKEN_3']};r=requests.get('https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter',headers=headers,params={'limit':1000,'offset':0},timeout=45);r.raise_for_status();goods=r.json()['data']['listGoods'];assert len(goods)<1000 and all(g['currencyIsoCode4217']=='CNY'for g in goods)
  mapping={s['sizeID']:g['nmID']for g in goods for s in g['sizes']};assert 0<len(mapping)<=1000
  r=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/2126188',headers=headers,json={'chrtIds':sorted(mapping)},timeout=45);r.raise_for_status();stocks=r.json()['stocks'];seen=set();amounts={}
  for x in stocks:
   ch=x['chrtId'];assert ch in mapping and ch not in seen and type(x['amount']) is int and x['amount']>=0;seen.add(ch);nm=mapping[ch];amounts[nm]=amounts.get(nm,0)+x['amount']
  complete={nm:all(ch in seen for ch,n in mapping.items() if n==nm)for nm in set(mapping.values())};now=datetime.now(timezone.utc).isoformat();latest=c.get('china_agent:hourly_sales_api:v1:latest')or{};hour=c.get(latest.get('source_key',''))or{};campaigns=hour.get('advertising',{}).get('campaigns',{})
  memberships=[]
  for cp in campaigns.values():
   if cp['status'] not in (4,9,11):continue
   for n in cp.get('nm_settings',[]):
    memberships.append(dict(nm=n['nm_id'],campaign=cp['id'],name=cp.get('settings',{}).get('name',''),status=cp['status'],bid_search=n.get('bids_kopecks',{}).get('search',0)/100,bid_recommendations=n.get('bids_kopecks',{}).get('recommendations',0)/100,asof=hour.get('observed_at')))
  old=c.get(ROOT+':details')or{};samples=old.get('price_samples',[]);samples+=[dict(nm=g['nmID'],date=now[:10],asof=now,price=g['sizes'][0]['discountedPrice'])for g in goods if len({s['discountedPrice']for s in g['sizes']})==1];samples=[s for s in samples if s['date']>=now[:7]+'-01']
  out=dict(status='complete',asof=now,warehouse_id=2126188,stock=[dict(nm=g['nmID'],article=g['vendorCode'],amount=amounts.get(g['nmID']) if complete[g['nmID']]else None)for g in goods],campaigns=memberships,campaigns_asof=hour.get('observed_at'),price_samples=samples,wb_writes=0,telegram_calls=0)
  c.put(ROOT+':details',out);print('Dashboard details saved',len(goods),len(memberships))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':refresh()
