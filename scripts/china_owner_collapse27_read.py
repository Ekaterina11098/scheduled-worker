"""Exact 25/26 November China FBS diagnostic; reads only, no Telegram."""
import os,json,requests
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
from china_hourly_sales_read import read_orders,select_rows,aggregate
c=Cache();ROOT='china_agent:owner_sales_collapse27:v1';MSK=ZoneInfo('Europe/Moscow')
if c.get(ROOT+':full_fbs'):raise SystemExit('Existing saved result; not repeating reads')
original=requests.sessions.Session.request
calls=[]
def guarded(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper();assert (u.hostname==urlparse(c.url).hostname and u.path.startswith('/rest/v1/') and m in('GET','POST','PATCH')) or(u.hostname=='marketplace-api.wildberries.ru' and m=='GET' and u.path in('/api/v3/orders','/api/v3/orders/new')),'Read only';return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guarded
def get(path,params=None):
 calls.append(path);r=requests.get('https://marketplace-api.wildberries.ru'+path,headers={'Authorization':os.environ['WB_TOKEN_3']},params=params,timeout=55);r.raise_for_status();return r.json()
start=datetime(2026,11,25,tzinfo=MSK);end=datetime(2026,11,27,tzinfo=MSK)
rows=read_orders(get,start,end);new=get('/api/v3/orders/new')['orders'];assert isinstance(new,list)
rows.update({r['id']:r for r in new});out=dict(observed_at=datetime.now(timezone.utc).isoformat(),status='complete',wb_writes=0,telegram_calls=0,wb_reads=len(calls),days={})
for offset in range(2):
 a=start+timedelta(days=offset);b=a+timedelta(days=1);part=select_rows(rows.values(),a,b);tot=aggregate(part);assert not tot['unknown_amount_ids'];by={};hours={}
 for r in part:
  nm=str(r['nmId']);v=by.setdefault(nm,dict(nm=int(nm),count=0,amount_cny=0));v['count']+=1;v['amount_cny']+=r['convertedPrice']/100
  hour=datetime.fromisoformat(r['createdAt'].replace('Z','+00:00')).astimezone(MSK).hour;v=hours.setdefault(str(hour),dict(count=0,amount_cny=0));v['count']+=1;v['amount_cny']+=r['convertedPrice']/100
 out['days'][str(a.date())]=dict(totals=tot,products=by,hours=hours)
c.put(ROOT+':full_fbs',out);print(json.dumps({k:v['totals']for k,v in out['days'].items()}))
