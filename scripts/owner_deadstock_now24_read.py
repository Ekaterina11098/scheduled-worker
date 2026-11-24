"""Bounded read-only 25 deadstock review; partial stages durable, no TG/model."""
import copy,json,requests,os,time
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
ROOT='china_agent:owner_deadstock_now:2026-11-24:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='POST'and u.path=='/api/analytics/v3/sales-funnel/products')or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and u.path=='/api/v3/stocks/2126188')or((u.hostname or'').endswith('moysklad.ru')and m=='GET')
  assert ok,'Read-only deadstock scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v['status']=='complete':print('Already complete');return
 if not v:v=dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 def save():io.put(ROOT,copy.deepcopy(v))
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:200]
  save()
 items=copy.deepcopy(io.get('china_agent:owner_deadstock:2026-11-23:v1:scope')['items'])
 items.append(dict(nm_id=2344552267,article='018-JuneBag-black'))
 assert len(items)==25 and len({i['nm_id']for i in items})==25
 v['items']=items;ids=[i['nm_id']for i in items]
 stage('prices',lambda:current_prices(io,ids))
 stage('stock',lambda:read_stock([i['article']for i in items],warehouse_role='msk'))
 if 'prices'in v:stage('published',lambda:published_stock(io,v['prices'],ids))
 def funnel(start,end,past):
  body=dict(selectedPeriod=dict(start=start,end=end),pastPeriod=dict(start=past,end=past),nmIds=ids,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy=dict(field='openCard',mode='desc'),limit=100,offset=0)
  r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=(10,60));r.raise_for_status();j=r.json()
  data=j['data'];assert data['currency']=='CNY'
  rows=data['products'];assert len(rows)<=25 and len({r['product']['nmId']for r in rows})==len(rows)
  wanted={i['nm_id']:i['article'].casefold()for i in items}
  assert all(r['product']['nmId']in wanted and r['product']['vendorCode'].casefold()==wanted[r['product']['nmId']]for r in rows)
  return dict(observed_at=now(),request=body,response=j)
 stage('today_vs_yesterday',lambda:funnel('2026-11-24','2026-11-24','2026-11-23'))
 time.sleep(21)
 stage('before',lambda:funnel('2026-11-22','2026-11-22','2026-11-21'))
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());save()
 print(json.dumps(dict(status=v['status'],items=25,errors=v['errors'],observed_at=v['observed_at'],completed_at=v['completed_at'])))
if __name__=='__main__':main()
