"""Owner second group301: exact warehouse stock reads, preserve every SKU."""
import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
ROOT='china_agent:owner_group2_stock27:v1';BASE='https://api.moysklad.ru/api/remap/1.2'
c=Cache();scope=c.get(ROOT+':scope');assert len(scope['items'])==301
out=c.get(ROOT+':result')or dict(status='reading',started_at=datetime.now(timezone.utc).isoformat(),warehouses={},errors={},wb_writes=0,moysklad_writes=0,telegram_calls=0)
if out.get('status')=='complete':raise SystemExit('Already saved')
original=requests.sessions.Session.request
roles={'msk':'3c67619d-f25d-11ee-0a80-0c6f000a027a','guangzhou':'2233c6a7-d906-11f1-0a80-197e004df0d2'}
wanted={x['article'].casefold()for x in scope['items']}
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(c.url).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH'))or(u.hostname=='api.moysklad.ru'and m=='GET'and u.path in('/api/remap/1.2/entity/store','/api/remap/1.2/report/stock/all'))
 assert ok,'Read-only warehouses and stock';return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip','Accept':'application/json;charset=utf-8'}
def pages(path,params):
 rows=[];size=None
 for page in range(12):
  r=requests.get(BASE+path,headers=headers,params=dict(params,limit=1000,offset=len(rows)),timeout=(10,50));r.raise_for_status();j=r.json();part=j['rows'];expected=j['meta']['size'];assert isinstance(part,list)and type(expected)is int
  if size is not None:assert size==expected,'Stock changed during pagination'
  size=expected;rows+=part
  if len(rows)==size:return rows
  assert part and len(rows)<size;time.sleep(.4)
 raise ValueError('Stock pagination exceeds bound')
try:
 stores=pages('/entity/store',{});bindings={role:[s for s in stores if s['id']==sid]for role,sid in roles.items()};assert all(len(s)==1 and not s[0].get('archived')for s in bindings.values())
 for role,sid in roles.items():
  if role in out['warehouses']:continue
  try:
   sh=bindings[role][0];assert sh['meta']['href']==BASE+'/entity/store/'+sid
   raw=pages('/report/stock/all',{'filter':'store='+sh['meta']['href']+';stockMode=all;quantityMode=all;archived=true;archived=false'});groups={}
   for r in raw:
    article=str(r.get('article',''))
    if article.casefold()not in wanted:continue
    groups.setdefault(article.casefold(),[]).append(r)
   rows=[]
   for item in scope['items']:
    rr=groups.get(item['article'].casefold(),[]);v=dict(nm=item['nm'],article=item['article'],status='missing'if not rr else'ambiguous'if len(rr)!=1 else'known',stock=None,reserve=None,available=None)
    if len(rr)==1:
     r=rr[0];assert all(type(r.get(k))in(int,float)for k in('stock','reserve'));v.update(stock=r['stock'],reserve=r['reserve'],available=r['stock']-r['reserve'])
    rows.append(v)
   out['warehouses'][role]=dict(id=sid,name=sh['name'],observed_at=datetime.now(timezone.utc).isoformat(),rows=rows,report_rows=len(raw),basis='stock-reserve');out['errors'].pop(role,None)
  except Exception as e:out['errors'][role]=type(e).__name__+': '+str(e)[:200]
  c.put(ROOT+':result',copy.deepcopy(out))
 out['status']='complete'if len(out['warehouses'])==2 and not out['errors']else'partial';out['completed_at']=datetime.now(timezone.utc).isoformat();c.put(ROOT+':result',out);print(json.dumps({k:{'rows':len(v['rows']),'known':sum(x['status']=='known'for x in v['rows'])}for k,v in out['warehouses'].items()}))
finally:requests.sessions.Session.request=original
