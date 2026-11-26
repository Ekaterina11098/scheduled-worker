"""Owner79 read only content and reviews, exact bounded endpoints, no TG/model."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
c=Cache();ROOT='china_agent:owner_cart79_27:v1';scope=c.get(ROOT+':scope');ids={x['nm']for x in scope['items']};assert len(ids)==79
out=c.get(ROOT+':result')or dict(status='reading',errors={},started_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0)
if out.get('status')=='complete':raise SystemExit('Already saved')
original=requests.sessions.Session.request
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper()
 ok=(u.hostname==urlparse(c.url).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='content-api.wildberries.ru'and m=='POST'and u.path=='/content/v2/get/cards/list')or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='feedbacks-api.wildberries.ru'and m=='GET'and u.path=='/api/v1/feedbacks')
 assert ok,'Only content, price, review reads';return original(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
headers={'Authorization':os.environ['WB_TOKEN_3']}
def req(host,path,params=None,body=None):
 time.sleep(.8);r=requests.request('POST'if body is not None else'GET','https://'+host+path,params=params,json=body,headers=headers,timeout=(8,35))
 if not r.ok:raise ValueError('HTTP '+str(r.status_code)+' '+host+path)
 return r.json()
def stage(k,fn):
 if k in out:return
 try:out[k]=dict(observed_at=datetime.now(timezone.utc).isoformat(),data=fn());out['errors'].pop(k,None)
 except Exception as e:out['errors'][k]=str(e)[:220]
 c.put(ROOT+':result',out)
try:
 def cards():
  cursor={'limit':100};rows=[];seen=set()
  for page in range(8):
   j=req('content-api.wildberries.ru','/content/v2/get/cards/list',body={'settings':{'cursor':cursor,'filter':{'withPhoto':-1}}});part=j['cards']
   for x in part:
    if x['nmID']in ids:rows.append(x)
   nxt=j['cursor']
   if nxt['total']<100:return {'rows':rows,'missing_ids':sorted(ids-{x['nmID']for x in rows}),'pages':page+1}
   marker=(nxt.get('updatedAt'),nxt.get('nmID'));assert marker not in seen;seen.add(marker);cursor={'limit':100,'updatedAt':nxt['updatedAt'],'nmID':nxt['nmID']}
  raise ValueError('Content exceeds8pages')
 stage('cards',cards)
 def prices():
  rows=[]
  for page in range(3):
   part=req('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',params={'limit':1000,'offset':page*1000})['data']['listGoods'];rows+=part
   if len(part)<1000:return [x for x in rows if x['nmID']in ids]
  raise ValueError('Prices exceed3pages')
 stage('prices',prices)
 # Strip reviewer identifiers, keep only product and review content required for audit.
 for answered in('false','true'):
  def reviews(answered=answered):
   j=req('feedbacks-api.wildberries.ru','/api/v1/feedbacks',params={'isAnswered':answered,'take':5000,'skip':0,'order':'dateDesc','dateFrom':int(datetime(2026,8,28,tzinfo=timezone.utc).timestamp()),'dateTo':int(datetime.now(timezone.utc).timestamp())})
   raw=j['data']['feedbacks'];rows=[]
   for x in raw:
    pd=x.get('productDetails')or{}
    if pd.get('nmId')in ids:rows.append({'id':x['id'],'nm':pd['nmId'],'date':x.get('createdDate'),'rating':x.get('productValuation'),'text':x.get('text'),'pros':x.get('pros'),'cons':x.get('cons'),'productDetails':{k:pd.get(k)for k in('nmId','supplierArticle','productName','size')}})
   return {'rows':rows,'total_page_rows':len(raw),'coverage_complete_in_requested_range':len(raw)<5000,'period_from':'2026-08-28','isAnswered':answered}
  stage('reviews_'+answered,reviews)
 out['status']='complete_with_gaps'if out['errors']else'complete';out['completed_at']=datetime.now(timezone.utc).isoformat();c.put(ROOT+':result',out);print(json.dumps({'status':out['status'],'errors':out['errors']}))
finally:requests.sessions.Session.request=original
