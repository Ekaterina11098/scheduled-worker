"""Exact one-campaign owner archive; no money, products, model or delivery endpoints."""
import os,json,time,hashlib,base64,datetime,requests
from china_codex_cloud import DB,stamp
ROOT='ooo_agent:umbrella_archive:2026-11-16:v1'
def run():
 db=DB();auth=db.get(ROOT+':authorization')or{}
 if auth.get('status')!='approved'or auth.get('campaign')!=39605579 or auth.get('cabinet')!='token_1'or auth.get('action')!='archive'or auth.get('telegram_allowed')is not False:raise RuntimeError('Exact approval required')
 s=db.get(ROOT+':execution')
 if s and s.get('status')=='verified':return
 if not s:s={'status':'preflight','steps':{},'started_at':stamp(),'run_id':os.environ['GITHUB_RUN_ID'],'telegram_calls':0,'model_calls':0};db.once(ROOT+':execution',s)
 def save():
  if not db.update(ROOT+':execution',s):raise RuntimeError('Receipt persistence failed')
 token=os.environ['WB_TOKEN_1'];claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
 ident=db.api('GET','analytics_snapshots',{'cabinet':'eq.token_1','source':'eq.seller_identity','status':'eq.complete','select':'payload','limit':100})
 if claims.get('exp',0)<=time.time()or claims.get('t')is not False or{r['payload'].get('sid')for r in ident}!={claims.get('sid')}:raise RuntimeError('OOO identity mismatch')
 def get(path,params=None,write=False):
  if path not in('/api/advert/v2/adverts','/adv/v0/stop','/adv/v1/promotion/count'):raise RuntimeError('Endpoint denied')
  old=s['steps'].get('archive')if write else None
  if old and old['status']=='accepted':return old['response']
  if old and old['status']not in('rejected_429',):raise RuntimeError('Uncertain/rejected step cannot be replayed')
  key='wb-pause:'+hashlib.sha256((token+'advert-api.wildberries.ru'+path).encode()).hexdigest()
  for attempt in range(6):
   wait=float((db.get(key)or{}).get('until',0))-time.time()
   while wait>0:
    s.update(status='waiting_shared_quota',waiting_path=path,resume_after=time.time()+wait);save();time.sleep(min(30,wait+1));wait=float((db.get(key)or{}).get('until',0))-time.time()
   if write:
    if db.get(ROOT+':authorization')!=auth or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(auth['expires_at']):raise RuntimeError('Authorization changed/expired')
    s['steps']['archive']={'status':'submitting','submitted_at':stamp()};save()
   try:r=requests.get('https://advert-api.wildberries.ru'+path,params=params,headers={'Authorization':token},timeout=(10,60),allow_redirects=False)
   except requests.RequestException:
    if write:s['steps']['archive']['status']='uncertain';save();raise
    time.sleep(5);continue
   try:delay=float(r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or r.headers.get('X-Ratelimit-Reset')or 0)
   except ValueError:delay=0
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or(r.headers.get('X-Ratelimit-Remaining')=='0'and delay>0):
    p={'until':time.time()+max(60,delay)+3,'basis':'provider_header'}
    db.update(key,p)if db.get(key)else db.once(key,p)
   if r.status_code==429:
    if write:s['steps']['archive'].update(status='rejected_429',http_status=429);save()
    continue
   if r.status_code!=200:
    if write:s['steps']['archive'].update(status='rejected',http_status=r.status_code);save()
    raise RuntimeError('WB HTTP '+str(r.status_code)+' '+path)
   data=r.json()if r.content else{}
   if write:s['steps']['archive'].update(status='accepted',http_status=200,response=data,accepted_at=stamp());save()
   return data
  raise RuntimeError('Provider read retry exhausted')
 try:
  if not s.get('before'):
   rows=get('/api/advert/v2/adverts',{'ids':'39605579'})['adverts']
   if len(rows)!=1 or rows[0]['id']!=39605579 or rows[0].get('currency')!='KGS'or rows[0]['status']not in(11,7):raise RuntimeError('Unexpected campaign baseline')
   s['before']=rows[0];save()
  if s['before']['status']!=7:get('/adv/v0/stop',{'id':39605579},write=True)
  counts=get('/adv/v1/promotion/count')
  matches=[g for g in counts.get('adverts',[])if any(c.get('advertId')==39605579 for c in g.get('advert_list',[]))]
  if len(matches)!=1 or matches[0]['status']!=7:raise RuntimeError('Archive status not confirmed')
  s.update(status='verified',after_status=7,verified_at=stamp(),status_readback=matches[0]);save()
  print('Owner archive verified; no messages or financial/product changes')
 except Exception as e:s.update(status='attention',safe_error=str(e));save();raise
if __name__=='__main__':run()
