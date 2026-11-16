"""One exact owner-approved OOO package. Private durable receipts, no Telegram/model calls."""
import os,json,time,hashlib,base64,copy,datetime,requests
from china_codex_cloud import DB as BaseDB,stamp
TASK='ooo_agent:regina_apply:2026-11-16:v1'
ROOT='ooo_agent:sol_dialog:v1:'
class Stop(Exception):pass
class Deferred(Exception):pass
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def valid_deposit_receipt(r):return r.get('currency')in(None,'KGS')and type(r.get('total'))in(int,float)and r['total']>=0
class DB(BaseDB):
 def once(self,key,value):
  rows=self.api('POST','telegram_api_cache',body={'cache_key':key,'payload':value,'updated_at':stamp(),'expires_at':'2030-11-16T00:00:00Z'})
  if len(rows)!=1 or self.get(key)!=value:raise Stop('Durable receipt claim failed')
 def put(self,key,value):
  return self.update(key,value)if self.get(key)is not None else self.once(key,value)
class Executor:
 def __init__(self,db,token,guard):
  self.db=db;self.token=token
  def request(method,url,**kw):
   if(method,url.removeprefix('https://advert-api.wildberries.ru'))not in {('GET','/api/advert/v2/adverts'),('PATCH','/adv/v0/auction/nms'),('PATCH','/api/advert/v1/bids'),('GET','/adv/v0/start'),('GET','/adv/v0/pause'),('GET','/adv/v0/stop'),('POST','/api/advert/v2/budget'),('GET','/adv/v1/balance'),('GET','/api/advert/v1/config'),('POST','/adv/v1/budget/deposit')}:raise Stop('Endpoint denied')
   if method=='PATCH'or url.endswith(('/adv/v0/start','/adv/v0/pause','/adv/v0/stop','/adv/v1/budget/deposit')):guard()
   return requests.request(method,url,**kw)
  self.request=request
 def call(self,s,save,method,path,body=None,params=None,step=None):
   allowed={('GET','/api/advert/v2/adverts'),('PATCH','/adv/v0/auction/nms'),('PATCH','/api/advert/v1/bids'),('GET','/adv/v0/start'),('GET','/adv/v0/pause'),('GET','/adv/v0/stop'),('POST','/api/advert/v2/budget'),('GET','/adv/v1/balance'),('GET','/api/advert/v1/config'),('POST','/adv/v1/budget/deposit')}
   if(method,path)not in allowed:raise Stop('Endpoint outside scope')
   old=s.setdefault('steps',{}).get(step)if step else None
   if old:
    if old['status']=='accepted':return old.get('response',{})
    if old['status']not in('rejected_429',):raise Stop('Write retained; no replay of '+old['status'])
   pause='wb-pause:'+hashlib.sha256((self.token+'advert-api.wildberries.ru'+path).encode()).hexdigest()
   until=float((self.db.get(pause)or{}).get('until',0))
   if until>time.time():s.update(resume_after=until,waiting_path=path);save();raise Deferred()
   if step:s['steps'][step]={'status':'submitting','path':path,'method':method,'body':body,'params':params,'submitted_at':stamp()};save()
   try:r=self.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':self.token},json=body,params=params,timeout=(10,60),allow_redirects=False)
   except requests.RequestException:
    if step:s['steps'][step]['status']='uncertain';save()
    raise Stop('Transport outcome uncertain; no automatic replay')from None
   try:data=r.json()
   except ValueError:data={'response_text':r.text[:2000]}
   raw=r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or r.headers.get('X-Ratelimit-Reset')
   try:delay=float(raw or 0)
   except ValueError:delay=0
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or(r.headers.get('X-Ratelimit-Remaining')=='0'and delay>0):self.db.put(pause,{'until':max(until,time.time()+max(delay,60)+3),'basis':'provider_header'})
   s.setdefault('last_http',{})[path]={'http_status':r.status_code,'response':data,'observed_at':stamp()};save()
   if r.status_code==429:
    if step:s['steps'][step].update(status='rejected_429',http_status=429);save()
    raise Deferred()
   if not 200<=r.status_code<300:
    if step:s['steps'][step].update(status='rejected',http_status=r.status_code,response=data);save()
    raise Stop('WB rejected HTTP '+str(r.status_code)+' '+path)
   if step:s['steps'][step].update(status='accepted',http_status=r.status_code,response=data,accepted_at=stamp());save()
   return data
 def fund(self,s,save,t,step):
   old=s.get('steps',{}).get(step)
   if old and old['status']=='accepted':return
   amount=t['amount_kgs'];cid=t['cid']
   if step=='deposit_39605581_500_repair1':
    rejected=s.get('steps',{}).get('deposit_39605581_500',{})
    if cid!=39605581 or amount!=500 or rejected.get('status')!='rejected'or rejected.get('http_status')!=400 or rejected.get('body',{}).get('sum')!=500 or rejected.get('body',{}).get('type')not in(0,1)or rejected.get('params')!={'id':cid}:raise Stop('Known rejected exact funding receipt required')
    # One explicitly authorized diagnostic retry, same amount and source. No wallet switch.
    receipt=self.call(s,save,'POST','/adv/v1/budget/deposit',{'sum':500,'type':rejected['body']['type'],'return':True},params={'id':cid},step=step)
    if not valid_deposit_receipt(receipt):raise Stop('Accepted deposit receipt requires reconciliation; never replay')
    return
   constraint=self.db.get(ROOT+'funding_constraints')or{}
   if constraint.get('currency')=='KGS'and amount<constraint.get('min_topup_kgs',0):raise Stop('Approved funding is below provider minimum; separate approval required')
   # Capture diagnostic evidence before any known-rejected retry. Never round approval up.
   if not s.get('funding_config_checked_at'):
    try:s['funding_config']=self.call(s,save,'GET','/api/advert/v1/config')
    except Stop:
     if s.get('last_http',{}).get('/api/advert/v1/config',{}).get('http_status')not in(401,403):raise
    s['funding_config_checked_at']=stamp();save()
   cfg=s.get('funding_config',{})
   if cfg and cfg.get('currency')!='KGS':raise Stop('Funding configuration currency differs')
   if cfg.get('minTopUp',0)>amount*100:raise Stop('Approved funding is below provider minimum; separate approval required')
   b=([s['funding_before']]if step=='deposit_39605581_500_repair1'and s.get('funding_before',{}).get('advertId')==cid else self.call(s,save,'POST','/api/advert/v2/budget',{'advertIds':[cid]})['adverts'])
   wallet=self.call(s,save,'GET','/adv/v1/balance')
   if len(b)!=1 or b[0].get('advertId')!=cid or b[0].get('currency')!='KGS'or wallet.get('currency')!='KGS':raise Stop('Funding currency/readback mismatch')
   source=0 if wallet.get('balance',0)>=amount else 1 if wallet.get('net',0)>=amount else None
   if source is None:raise Stop('Insufficient wallet; funding not submitted')
   s.setdefault('funding_before_by_campaign',{})[str(cid)]=b[0];s['funding_wallet']=wallet;save()
   receipt=self.call(s,save,'POST','/adv/v1/budget/deposit',{'sum':amount,'type':source,'return':True},params={'id':cid},step=step)
   if not valid_deposit_receipt(receipt):raise Stop('Accepted deposit receipt requires reconciliation; never replay')
 
def project(c):
 return {k:copy.deepcopy(c.get(k))for k in ['id','status','currency','bid_type','settings']}|{'nm_settings':sorted(copy.deepcopy(c['nm_settings']),key=lambda n:n['nm_id'])}
def run():
 db=DB();auth=db.get(TASK+':authorization')or{}
 if auth.get('status')!='approved'or auth.get('cabinet')!='token_1'or auth.get('currency')!='KGS'or auth.get('telegram_allowed')is not False:raise Stop('Exact authorization required')
 if auth.get('campaign')!=39605581 or set(auth.get('keep_nm_ids',[]))!={851230666,1140798740,863222656}or auth.get('search_minor')!=325 or auth.get('recommendations_minor')!=325 or auth.get('deposit_kgs')!=1200 or auth.get('resume')is not True or set(auth.get('archive_ids',[]))!={41515989,41516310,41516903,41517233,41517533,39605582}:raise Stop('Scope mismatch')
 s=db.get(TASK+':execution')
 if s and s.get('status')=='verified':print('Already verified; no replay');return
 if s and s.get('status')=='attention':raise Stop('Attention requires reconciliation, no replay')
 if not s:
  s={'status':'preflight','steps':{},'authorization_sha256':hashlib.sha256(canonical(auth).encode()).hexdigest(),'started_at':stamp(),'run_id':os.environ['GITHUB_RUN_ID'],'telegram_calls':0,'model_calls':0}
  db.once(TASK+':execution',s)
 def save():
  v=json.loads(json.dumps(s))
  if not db.update(TASK+':execution',v):raise Stop('Receipt persistence failed')
 def guard():
  if db.get(TASK+':authorization')!=auth:raise Stop('Authorization changed')
  if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(auth['expires_at']):raise Stop('Authorization expired before write')
 token=os.environ['WB_TOKEN_1'];claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
 identity=db.api('GET','analytics_snapshots',{'cabinet':'eq.token_1','source':'eq.seller_identity','status':'eq.complete','select':'payload','limit':100})
 if claims.get('exp',0)<=time.time()or claims.get('t')is not False or int(claims.get('s',0))&(1<<30)or {x['payload'].get('sid')for x in identity}!={claims.get('sid')}:raise Stop('OOO identity mismatch')
 ex=Executor(db,token,guard);allids=[39605581,39605579,40385586,41515989,41516310,41516903,41517233,41517533,39605582]
 def call(method,path,body=None,params=None,step=None):return ex.call(s,save,method,path,body,params,step)
 def configs():
  data=call('GET','/api/advert/v2/adverts',params={'ids':','.join(map(str,allids))})
  out={str(c['id']):c for c in data['adverts']}
  if set(out)!=set(map(str,allids)):raise Stop('Readback coverage incomplete')
  return out
 deadline=time.time()+165*60
 while time.time()<deadline:
  try:
   if not s.get('before'):
    before=configs();main=before['39605581'];keep=set(auth['keep_nm_ids'])
    if any(c.get('currency')!='KGS'for c in before.values()):raise Stop('Currency mismatch')
    if main['status']not in(9,11)or main['bid_type']!='manual'or main['settings']['payment_type']!='cpc'or main['settings']['placements']!={'search':True,'recommendations':True}:raise Stop('Unsupported main baseline')
    if not keep<={n['nm_id']for n in main['nm_settings']}or not main['restrictions'].get('can_change_nms'):raise Stop('Target composition unavailable')
    if any(before[str(cid)]['status']not in(11,7)for cid in auth['archive_ids']):raise Stop('Archive baseline must be paused or already completed')
    expected=copy.deepcopy(before);target=expected['39605581'];target['nm_settings']=[n for n in target['nm_settings']if n['nm_id']in keep];target['status']=9
    for n in target['nm_settings']:n['bids_kopecks'].update(search=325,recommendations=325)
    for cid in auth['archive_ids']:expected[str(cid)]['status']=7
    s.update(before=before,expected=expected,baseline_observed_at=stamp(),delete_nm_ids=sorted({n['nm_id']for n in main['nm_settings']}-keep),bid_changes=[{'nm_id':n['nm_id'],'placement':p,'bid_kopecks':325}for n in main['nm_settings']if n['nm_id']in keep for p in ['search','recommendations']if n['bids_kopecks'].get(p)!=325]);save()
   if s['before']['39605581']['status']==9:call('GET','/adv/v0/pause',params={'id':39605581},step='pause_main')
   if s['delete_nm_ids']:call('PATCH','/adv/v0/auction/nms',{'nms':[{'advert_id':39605581,'nms':{'add':[],'delete':s['delete_nm_ids']}}]},step='memberships')
   if s['bid_changes']:call('PATCH','/api/advert/v1/bids',{'bids':[{'advert_id':39605581,'nm_bids':s['bid_changes']}]},step='bids')
   ex.fund(s,save,{'cid':39605581,'amount_kgs':1200},'deposit_39605581_1200')
   if not s.get('funding_verified_at'):
    b=call('POST','/api/advert/v2/budget',{'advertIds':[39605581]})['adverts']
    if len(b)!=1 or b[0].get('advertId')!=39605581 or b[0].get('currency')!='KGS'or b[0].get('total',-1)<s['funding_before_by_campaign']['39605581']['total']+1200:raise Stop('Accepted deposit needs reconciliation, never replay')
    s.update(funding_after=b[0],funding_verified_at=stamp());save()
   call('GET','/adv/v0/start',params={'id':39605581},step='start_main')
   for cid in auth['archive_ids']:
    if s['before'][str(cid)]['status']!=7:call('GET','/adv/v0/stop',params={'id':cid},step='archive_'+str(cid))
   after=configs()
   for cid,expected in s['expected'].items():
    if project(after[cid])!=project(expected):raise Stop('Configuration readback differs at '+cid)
   s.update(after=after,status='verified',verified_at=stamp());save()
   print('Exact approved package verified; no Telegram/model calls');return
  except Deferred:
   s['status']='waiting_shared_quota';save()
   while time.time()<float(s.get('resume_after',0)):
    if time.time()>deadline:raise Stop('Quota wait exceeds job window; retained receipts')
    time.sleep(min(30,max(.1,float(s['resume_after'])-time.time())))
  except Exception as err:
   s.update(status='attention',safe_error=str(err)if isinstance(err,Stop)else type(err).__name__);save();raise
 raise Stop('Execution window elapsed; retained receipts')
if __name__=='__main__':run()
