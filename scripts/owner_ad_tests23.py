"""Owner-scoped, model-free advertising test preparation; no marketplace mutations."""
import base64,datetime,hashlib,json,os,time
from urllib.parse import urlparse
import requests
ROOT='owner_ads_test:2026-11-23:v1'
REPO='Ekaterina11098/scheduled-worker'
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class State:
 def __init__(self):
  self.base=os.environ['SUPABASE_URL'].rstrip('/')
  self.secret=os.environ['SUPABASE_SECRET_KEY']
 def db(self,method,table,params=None,body=None,prefer=None):
  if table not in ('telegram_api_cache','analytics_snapshots'):raise PermissionError('DB table')
  h={'apikey':self.secret,'Prefer':prefer or 'return=representation'}
  if not self.secret.startswith('sb_secret_'):h['Authorization']='Bearer '+self.secret
  r=requests.request(method,self.base+'/rest/v1/'+table,headers=h,params=params,json=body,timeout=45,allow_redirects=False)
  if not r.ok:raise RuntimeError('State HTTP '+str(r.status_code))
  return r.json() if r.content else None
 def get(self,key):
  rows=self.db('GET','telegram_api_cache',{'cache_key':'eq.'+key,'select':'payload'})or[]
  return rows[0]['payload']if rows else None
 def put(self,key,value,once=False):
  return self.db('POST','telegram_api_cache',{'on_conflict':'cache_key'},dict(cache_key=key,payload=value,updated_at=stamp(),expires_at='2027-11-23T00:00:00Z'),
   'resolution='+('ignore'if once else'merge')+'-duplicates,return=representation')
class ReadWB:
 READS={('GET','advert-api.wildberries.ru','/adv/v1/promotion/count'),
        ('GET','advert-api.wildberries.ru','/api/advert/v1/config'),
        ('GET','advert-api.wildberries.ru','/api/advert/v2/adverts'),
        ('GET','advert-api.wildberries.ru','/adv/v1/balance'),
        ('GET','discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter'),
        ('POST','seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products')}
 def __init__(self,db,cabinet):self.db=db;self.cabinet=cabinet;self.token=os.environ['WB_TOKEN_'+cabinet[-1]]
 def identity(self):
  claim=json.loads(base64.urlsafe_b64decode(self.token.split('.')[1]+'==='))
  if claim.get('exp',0)<=time.time()or claim.get('t')is not False or int(claim.get('s',0))&(1<<30)or not claim.get('sid'):raise PermissionError('Invalid seller credential')
  rows=self.db.db('GET','analytics_snapshots',{'cabinet':'eq.'+self.cabinet,'source':'eq.seller_identity','status':'eq.complete','select':'payload','limit':100})or[]
  if {r['payload'].get('sid')for r in rows}!={claim['sid']}:raise PermissionError('Seller identity mismatch')
  return True
 def read(self,host,path,method='GET',params=None,body=None):
  if(method,host,path)not in self.READS:raise PermissionError('Read-only boundary')
  key='wb-pause:'+hashlib.sha256((self.token+host+path).encode()).hexdigest()
  until=float((self.db.get(key)or{}).get('until',0))
  if until>time.time():raise RuntimeError('Shared provider cooldown until '+datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat())
  time.sleep(1.3)
  r=requests.request(method,'https://'+host+path,headers={'Authorization':self.token},params=params,json=body,timeout=(10,70),allow_redirects=False)
  raw=r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or r.headers.get('X-Ratelimit-Reset')
  try:delay=float(raw or 0)
  except ValueError:delay=0
  if delay>time.time()-86400:delay=max(0,delay-time.time())
  if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0'and delay>0:
   self.db.put(key,{'until':time.time()+max(60,delay)+3,'basis':'provider_header'})
  if not r.ok:raise RuntimeError('WB read HTTP '+str(r.status_code)+' '+path)
  return r.json()
def collect(db,scope):
 w=ReadWB(db,scope['cabinet']);out=dict(status='reading',cabinet=scope['cabinet'],currency=scope['currency'],observed_at=stamp(),wb_writes=0,model_calls=0,stages={})
 key=ROOT+':preflight:'+scope['cabinet']
 if(db.get(key)or{}).get('status')=='complete':return db.get(key)
 def save():db.put(key,out)
 def stage(name,fn):
  try:out['stages'][name]=dict(status='complete',observed_at=stamp(),data=fn())
  except Exception as e:out['stages'][name]=dict(status='unavailable',observed_at=stamp(),error=str(e)if isinstance(e,(RuntimeError,ValueError,PermissionError))else type(e).__name__)
  save()
 try:
  w.identity();out['identity_verified']=True;save()
  stage('configuration',lambda:w.read('advert-api.wildberries.ru','/api/advert/v1/config'))
  stage('inventory',lambda:w.read('advert-api.wildberries.ru','/adv/v1/promotion/count'))
  stage('wallet',lambda:w.read('advert-api.wildberries.ru','/adv/v1/balance'))
  def configs():
   ids=sorted({r['advertId']for g in out['stages']['inventory']['data'].get('adverts',[])if g['status']in(4,9,11)for r in g.get('advert_list',[])})
   cs=[]
   for start in range(0,len(ids),50):cs+=w.read('advert-api.wildberries.ru','/api/advert/v2/adverts',params={'ids':','.join(map(str,ids[start:start+50]))})['adverts']
   if {c['id']for c in cs}!=set(ids)or any(c.get('currency')!=scope['currency']for c in cs):raise ValueError('Campaign coverage or currency mismatch')
   return cs
  stage('campaigns',configs)
  def prices():
   goods=[]
   for offset in range(0,10000,1000):
    part=w.read('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',params={'limit':1000,'offset':offset})['data']['listGoods'];goods+=part
    if len(part)<1000:return goods
   raise ValueError('Price catalogue truncated')
  stage('prices',prices)
  wanted=scope['initial']+scope['additional']
  stage('funnel',lambda:w.read('seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products','POST',body={'selectedPeriod':{'start':'2026-11-09','end':'2026-11-22'},'pastPeriod':{'start':'2026-10-26','end':'2026-11-08'},'nmIds':[r['nm']for r in wanted],'skipDeletedNm':False,'limit':1000,'offset':0}))
  out['status']='complete'if all(s['status']=='complete'for s in out['stages'].values())else'partial'
 except Exception as e:out.update(status='attention',error=str(e)if isinstance(e,(RuntimeError,ValueError,PermissionError))else type(e).__name__)
 out['finished_at']=stamp();save();return out
def main():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':raise PermissionError('Public main runner required')
 db=State();q=db.get(ROOT+':request')or{}
 if q.get('owner_id')!=5122667182 or q.get('wb_writes_allowed')is not False or q.get('status')!='read_only_requested':raise PermissionError('Read request missing')
 for scope in q['cabinets']:
  r=collect(db,scope);print(json.dumps({'cabinet':r['cabinet'],'status':r['status'],'wb_writes':0,'model_calls':0}))
if __name__=='__main__':main()
