"""Exact returned China articles: fresh read-only two warehouse stocks."""
import copy,json,time,os,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_moysklad_read import Reader
from urllib.parse import urlparse
io=AdvertisingIO();ROOT='china_agent:owner_returns_stock27:v1'
scope=io.get(ROOT+':scope');assert scope['start']=='2026-11-23'and scope['products']==163 and scope['unique_units']==933
articles=[x['article']for x in scope['rows']]
e=io.get(ROOT+':result')or dict(status='collecting',created_at=datetime.now(timezone.utc).isoformat(),warehouses={},wb_writes=0,moysklad_writes=0,telegram_calls=0)
def save():io.put(ROOT+':result',copy.deepcopy(e))
original=requests.sessions.Session.request
def guard(s,method,url,*a,**kw):
 u=urlparse(url)
 safe=u.hostname==urlparse(io.url).hostname and method.upper()in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
 safe=safe or u.hostname=='api.moysklad.ru'and method.upper()=='GET'and u.path in('/api/remap/1.2/entity/store','/api/remap/1.2/entity/product','/api/remap/1.2/report/stock/all')
 assert safe,'Readonly scope violated'
 return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
reader=Reader();oldget=reader.get;cache={}
def get(path,params):
 k=(path,json.dumps(params,sort_keys=True))
 if path in('/entity/store','/entity/product')and k in cache:return cache[k]
 r=oldget(path,params)
 if path in('/entity/store','/entity/product'):cache[k]=r
 return r
reader.get=get
save()
for role in('msk','guangzhou'):
 if role in e['warehouses']:continue
 try:e['warehouses'][role]=reader.stock(articles,role);save()
 except Exception as ex:
  e['status']='partial';e['error']=type(ex).__name__+':'+str(ex)[:200];save();raise
p=io.get('china_agent:sheet_dashboard:v1:details');wanted={x['nm']for x in scope['rows']}
e['published_wb_snapshot']={k:p[k]for k in('asof','warehouse_id')if k in p}|{'rows':[x for x in p.get('stock',[])if x.get('nm')in wanted]}
e['status']='complete';e['completed_at']=datetime.now(timezone.utc).isoformat();save()
print('Readonly returned article stock complete: '+str(len(articles)))
