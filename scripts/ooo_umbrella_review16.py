"""Owner-requested, one-shot cohort refresh. Only GET orders/sales; no delivery credentials."""
import os,json,time,base64,hashlib,collections,datetime
import requests
from china_codex_cloud import DB,stamp
ROOT='ooo_agent:umbrella_review:2026-11-16:v1'
HOST='statistics-api.wildberries.ru'
def summarize(orders,sales,ids):
 latest={}
 for x in sales:
  if x.get('srid') and (x.get('lastChangeDate',''),x.get('date',''),str(x.get('saleID','')).startswith('R')) >= latest.get(x['srid'],('','','')):
   latest[x['srid']]=(x.get('lastChangeDate',''),x.get('date',''),str(x.get('saleID','')).startswith('R'))
 out={}
 for name,start,end in [('old_comparable','2026-10-05','2026-10-28'),('mature_recent','2026-10-19','2026-11-02'),('recent_unmatured','2026-11-03','2026-11-15')]:
  rows={nm:collections.Counter()for nm in ids}
  unique={}
  for x in orders:
   if x.get('srid')and start<=x.get('date','')[:10]<=end:
    if x.get('lastChangeDate','')>=unique.get(x['srid'],{}).get('lastChangeDate',''):unique[x['srid']]=x
  for srid,x in unique.items():
   v=rows[x['nmId']];v['ordered']+=1
   if srid in latest:v['returned'if latest[srid][2]else'paid']+=1;v['closed']+=1
   elif x.get('isCancel'):v['cancelled']+=1;v['closed']+=1
   else:v['unresolved']+=1
  out[name]={'from':start,'to':end,'rows':[{'nm':nm,**dict(v)}for nm,v in rows.items()]}
 return out
def run():
 db=DB();existing=db.get(ROOT+':summary')or{}
 if existing.get('status')=='complete':print('Existing completed refresh retained');return
 token=os.environ['WB_TOKEN_1'];claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
 identity=db.api('GET','analytics_snapshots',{'cabinet':'eq.token_1','source':'eq.seller_identity','status':'eq.complete','select':'payload','limit':100})
 if claims.get('exp',0)<time.time()or{r['payload'].get('sid')for r in identity}!={claims.get('sid')}:raise PermissionError('OOO identity mismatch')
 e=db.get('ooo_agent:morning:2026-11-16:evidence')or{}
 latest=db.get('ooo_agent:regina_apply:2026-11-16:v1:execution')or{}
 cfg=next((r for r in latest.get('last_http',{}).get('/api/advert/v2/adverts',{}).get('response',{}).get('adverts',[])if r['id']==39605579),e['sources']['configurations']['data']['39605579']);ids={r['nm_id']for r in cfg['nm_settings']}
 if not db.get(ROOT+':configuration'):db.once(ROOT+':configuration',{'data':cfg,'observed_at':latest.get('last_http',{}).get('/api/advert/v2/adverts',{}).get('observed_at')})
 def stage(kind):
  path='/api/v1/supplier/'+kind;key=ROOT+':'+kind
  cached=db.get(key)
  if cached and cached.get('status')=='complete':return cached['rows']
  pausekey='wb-pause:'+hashlib.sha256((token+HOST+path).encode()).hexdigest()
  for attempt in range(4):
   pause=db.get(pausekey)or{};wait=float(pause.get('until',0))-time.time()
   if wait>7200:raise RuntimeError('Shared quota exceeds authorized read window')
   while wait>0:
    time.sleep(min(30,wait+1));wait=float((db.get(pausekey)or{}).get('until',0))-time.time()
   r=requests.get('https://'+HOST+path,params={'dateFrom':'2026-10-05T00:00:00','flag':0},headers={'Authorization':token},timeout=(10,90),allow_redirects=False)
   try:delay=float(r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or 60)
   except ValueError:delay=60
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0':
    v={'until':time.time()+max(60,delay)+3,'basis':'provider_header'}
    db.update(pausekey,v)if pause else db.once(pausekey,v)
   if r.status_code==429:continue
   if r.status_code!=200:raise RuntimeError('Read endpoint '+kind+' HTTP '+str(r.status_code))
   rows=r.json()
   if not isinstance(rows,list)or len(rows)>=80000:raise RuntimeError('Incomplete endpoint coverage; do not analyze')
   keep=['srid','nmId','date','lastChangeDate','isCancel']if kind=='orders'else['srid','nmId','date','lastChangeDate','saleID']
   filtered=[{k:x.get(k)for k in keep}for x in rows if x.get('nmId')in ids]
   value={'status':'complete','observed_at':stamp(),'provider_rows':len(rows),'rows':filtered}
   db.update(key,value)if cached else db.once(key,value)
   return filtered
  raise RuntimeError('Provider retry pending')
 orders=stage('orders');sales=stage('sales')
 value={'status':'complete','observed_at':stamp(),'cabinet':'token_1','campaign':39605579,'cohorts':summarize(orders,sales,ids),'wb_writes':0,'telegram_calls':0,'model_calls':0}
 db.once(ROOT+':summary',value)
 print('Private cohort refresh complete; no marketplace writes or messages')
def read_today():
 db=DB();key=ROOT+':today'
 if(db.get(key)or{}).get('status')=='complete':return
 token=os.environ['WB_TOKEN_1'];claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
 identity=db.api('GET','analytics_snapshots',{'cabinet':'eq.token_1','source':'eq.seller_identity','status':'eq.complete','select':'payload','limit':100})
 if claims.get('exp',0)<time.time()or {r['payload'].get('sid')for r in identity}!={claims.get('sid')}:raise PermissionError('OOO identity mismatch')
 host='advert-api.wildberries.ru';path='/adv/v3/fullstats';pausekey='wb-pause:'+hashlib.sha256((token+host+path).encode()).hexdigest()
 for attempt in range(4):
  pause=db.get(pausekey)or{};wait=float(pause.get('until',0))-time.time()
  if wait>240:raise RuntimeError('Advertising shared quota pending')
  if wait>0:time.sleep(wait+1)
  r=requests.get('https://'+host+path,params={'ids':'39605579','beginDate':'2026-11-16','endDate':'2026-11-16'},headers={'Authorization':token},timeout=(10,90),allow_redirects=False)
  try:delay=float(r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or r.headers.get('X-Ratelimit-Reset')or 0)
  except ValueError:delay=0
  if delay>time.time()-86400:delay=max(0,delay-time.time())
  if r.status_code==429 or(r.headers.get('X-Ratelimit-Remaining')=='0'and delay>0):
   v={'until':time.time()+max(60,delay)+3,'basis':'provider_header'}
   db.update(pausekey,v)if pause else db.once(pausekey,v)
  if r.status_code==429:continue
  if r.status_code!=200:raise RuntimeError('Advertising read HTTP '+str(r.status_code))
  rows=r.json()
  if not isinstance(rows,list)or any(x.get('currency')!='KGS'or x.get('advertId')!=39605579 for x in rows):raise RuntimeError('Advertising coverage/currency invalid')
  db.once(key,{'status':'complete'if rows else'missing_not_zero','observed_at':stamp(),'data':rows,'wb_writes':0});return
 raise RuntimeError('Advertising retry pending')
if __name__=='__main__':read_today();run()


