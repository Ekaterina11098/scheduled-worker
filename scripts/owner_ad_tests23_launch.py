"""Launch only two existing owner-approved test drafts, with bounded one-time funding."""
import datetime,hashlib,json,os,re,time
import requests
from owner_ad_tests23 import State,ReadWB,ROOT,REPO,stamp
HOST='advert-api.wildberries.ru'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate_authorization(a):
 if a.get('status')!='approved'or a.get('owner_id')!=5122667182 or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(a['expires_at']):raise PermissionError('Exact current owner authorization required')
 if a.get('initial_budget')!=1000 or a.get('fallback_budget')!=2000 or a.get('maximum_budget_per_campaign')!=2000 or a.get('fallback_only_on_explicit_minimum_rejection')is not True:raise PermissionError('Budget boundary changed')
 if any(a.get(k)is not False for k in ('auto_topup','existing_campaign_writes','new_campaign_creation','card_charge_allowed','paid_ai_allowed')):raise PermissionError('Forbidden capability')
 if {(x['cabinet'],x['currency'],x['campaign_id'],len(x['skus']))for x in a['items']}!={('token_2','RUB',42139004,18),('token_1','KGS',42139012,6)}or len(a['items'])!=2:raise PermissionError('Exact existing campaign scope required')
 for x in a['items']:
  if x['placements']!=['search']or x['payment_type']!='cpc'or x['bid_type']!='manual'or len({r['nm']for r in x['skus']})!=len(x['skus']):raise PermissionError('Campaign contract changed')
  if x['cabinet']=='token_2'and any(r['nm']==1007948808 for r in x['skus'])or x['cabinet']=='token_1'and any(r['nm']==851316021 for r in x['skus']):raise PermissionError('Protected SKU')
def validate_campaign(c,item,statuses,bids=None):
 if c.get('id')!=item['campaign_id']or c.get('currency')!=item['currency']or c.get('status')not in statuses or c.get('bid_type')!='manual':raise ValueError('Campaign identity/status/currency changed')
 if c.get('settings',{}).get('name')!=item['name']or c['settings'].get('payment_type')!='cpc'or c['settings'].get('placements')!={'search':True,'recommendations':False}:raise ValueError('Campaign placement/payment changed')
 if {n['nm_id']for n in c['nm_settings']}!={r['nm']for r in item['skus']}:raise ValueError('Campaign composition changed')
 if bids is not None and any(n.get('bids_kopecks',{}).get('search')!=bids[n['nm_id']]for n in c['nm_settings']):raise ValueError('Minimum bids not verified')
def parse_bids(value,item):
 out={}
 for n in value.get('bids',[]):
  bs=[b for b in n.get('bids',[])if b.get('type')=='search'and b.get('currency')==item['currency']]
  if n['nm_id']in out or len(bs)!=1 or type(bs[0].get('value'))is not int or bs[0]['value']<=0:raise ValueError('Ambiguous native minimum bid')
  out[n['nm_id']]=bs[0]['value']
 if set(out)!={r['nm']for r in item['skus']}:raise ValueError('Minimum bid coverage incomplete')
 return out
def stock_cache(db,item,now=None):
 now=now or datetime.datetime.now(datetime.timezone.utc);found=[]
 prior=db.get(ROOT+':launch:'+item['cabinet'])or{}
 if prior.get('stock_readback')and prior.get('stock_verified_at'):found.append((prior['stock_verified_at'],prior['stock_readback'],'earlier_verified_WB_read'))
 pre=db.get(ROOT+':preflight:'+item['cabinet'])or{};stage=pre.get('stages',{}).get('funnel',{})
 if stage.get('status')=='complete'and stage.get('observed_at'):
  found.append((stage['observed_at'],{str(r['product']['nmId']):r['product']for r in stage['data']['data']['products']},'saved_WB_preflight'))
 wanted={r['nm']:r['article']for r in item['skus']}
 for observed,raw,source in sorted(found,reverse=True,key=lambda x:x[0]):
  if not 0<=(now-datetime.datetime.fromisoformat(observed)).total_seconds()<=90*60:continue
  selected={int(n):p for n,p in raw.items()if int(n)in wanted}
  if set(selected)==set(wanted)and all(p.get('vendorCode')==wanted[n]and p.get('subjectId')==50 and p.get('stocks',{}).get('wb',0)>=3 and p.get('feedbackRating',0)>=4.5 for n,p in selected.items()):return selected,observed,source
 return None
class Rejected(RuntimeError):
 def __init__(self,status,detail):self.status=status;self.detail=detail;super().__init__('WB rejected HTTP '+str(status))
def minimum_rejection(exc):
 text=json.dumps(exc.detail,ensure_ascii=False).lower()
 return exc.status==400 and bool(re.search(r'minimum|minimal|min.?top.?up|budget.?too.?small|минималь|не менее|at least',text))
class Client:
 def __init__(self,db,auth,item,state,key):self.db=db;self.auth=auth;self.item=item;self.state=state;self.key=key;self.wb=ReadWB(db,item['cabinet']);self.deadline=time.time()+24*60
 def save(self):
  self.db.put(self.key,self.state)
  if self.db.get(self.key)!=json.loads(json.dumps(self.state)):raise RuntimeError('Financial journal not durable')
 def guard(self):
  validate_authorization(self.auth)
  if self.db.get(ROOT+':launch_authorization')!=self.auth:raise PermissionError('Authorization changed')
 def wait(self,path):
  pause='wb-pause:'+hashlib.sha256((self.wb.token+HOST+path).encode()).hexdigest()
  until=float((self.db.get(pause)or{}).get('until',0))
  if until>self.deadline:raise RuntimeError('Provider retry exceeds this run; no write')
  if until>time.time():
   self.state.update(waiting_path=path,resume_after=datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat());self.save()
   print(json.dumps({'cabinet':self.item['cabinet'],'status':'waiting_provider','resume_after':self.state['resume_after']}),flush=True)
  while until>time.time():self.guard();time.sleep(min(30,max(.2,until-time.time())))
  return pause
 def check_request(self,path,method,body,params,step):
  cid=self.item['campaign_id']
  if step=='bids':
   expected={'bids':[{'advert_id':cid,'nm_bids':[{'nm_id':int(n),'bid_kopecks':v,'placement':'search'}for n,v in sorted(self.state['minimum_bids'].items(),key=lambda x:int(x[0]))]}]}
   if(method,path,body)!=('PATCH','/api/advert/v1/bids',expected):raise PermissionError('Exact minimum bid update required')
  elif step in('deposit1000','deposit2000'):
   amount=1000 if step=='deposit1000'else 2000
   if(method,path,params,body)!=('POST','/adv/v1/budget/deposit',{'id':cid},{'sum':amount,'type':1,'return':True}):raise PermissionError('Exact one-time balance funding required')
   if step=='deposit2000'and self.state.get('fallback_minimum_rejection_verified')is not True:raise PermissionError('Fallback not justified')
  elif step=='start':
   if(method,path,params)!=('GET','/adv/v0/start',{'id':cid})or self.state.get('funding_verified')is not True or self.state.get('settings_verified')is not True:raise PermissionError('Unverified campaign cannot start')
  elif step:raise PermissionError('Unknown write')
  elif(method,path)not in {('GET','/api/advert/v2/adverts'),('GET','/adv/v1/promotion/count'),('POST','/api/advert/v2/budget'),('GET','/adv/v1/balance'),('POST','/api/advert/v1/bids/min')}:raise PermissionError('Unknown read')
 def call(self,path,method='GET',body=None,params=None,step=None):
  self.guard();self.check_request(path,method,body,params,step)
  if step and step in self.state['steps']:
   old=self.state['steps'][step]
   if old['status']=='accepted':return old.get('response',{})
   retry429=step=='deposit2000'and old['status']=='rejected'and old.get('http_status')==429 and self.state.get('fallback_minimum_rejection_verified')is True
   if not retry429:
    if old['status']=='rejected':raise Rejected(old['http_status'],old['detail'])
    raise RuntimeError('Prior write outcome unresolved; no repeat')
  for attempt in range(3 if not step else 1):
   pause=self.wait(path);self.guard()
   if step:
    old=self.state['steps'].get(step)
    if old:self.state.setdefault('prior_rejections',{}).setdefault(step,[]).append(json.loads(json.dumps(old)))
    self.state['steps'][step]=dict(status='submitting',path=path,body=body,params=params,at=stamp());self.save()
   time.sleep(2)
   try:r=requests.request(method,'https://'+HOST+path,headers={'Authorization':self.wb.token},params=params,json=body,timeout=(10,65),allow_redirects=False)
   except requests.RequestException:
    if step:self.state['steps'][step]['status']='uncertain';self.save()
    raise RuntimeError('Unknown transport result; no repeated financial/write request')from None
   raw=r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or r.headers.get('X-Ratelimit-Reset')
   try:delay=float(raw or 0)
   except ValueError:delay=0
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0'and delay>0:self.db.put(pause,{'until':time.time()+max(60,delay)+3,'basis':'provider_header'})
   if not r.ok:
    try:detail=r.json()
    except ValueError:detail={'message':r.text[:1500]}
    detail=json.loads(json.dumps(detail).replace(self.wb.token,'[redacted]'))
    if step:self.state['steps'][step].update(status='rejected',http_status=r.status_code,detail=detail);self.save()
    if r.status_code==429 and not step:continue
    raise Rejected(r.status_code,detail)
   try:value=r.json()if r.content else{}
   except ValueError:
    if step:self.state['steps'][step]['status']='uncertain';self.save()
    raise RuntimeError('Unparseable successful response; no write repetition')from None
   if step:self.state['steps'][step].update(status='accepted',response=value,accepted_at=stamp());self.save()
   return value
  raise RuntimeError('Read rate limit remains active')
 def campaign(self):
  rows=self.call('/api/advert/v2/adverts',params={'ids':str(self.item['campaign_id'])}).get('adverts',[])
  if len(rows)!=1:raise ValueError('Exact draft readback unavailable')
  return rows[0]
 def budget(self):
  cid=self.item['campaign_id'];rs=self.call('/api/advert/v2/budget','POST',{'advertIds':[cid]}).get('adverts',[])
  if len(rs)!=1 or rs[0].get('advertId')!=cid or rs[0].get('currency')!=self.item['currency']or type(rs[0].get('total'))is not int:raise ValueError('Native budget readback unavailable')
  return rs[0]['total']
 def prepare(self):
  # Accepted exact creation and zero balance establish an owned, unfunded target.
  # Use the scarce full-configuration read after the idempotent bid update,
  # before any funding, rather than spending it twice on the same draft.
  self.wb.identity()
  prior_budget=self.state.get('initial_budget_verified_at')
  reusable=prior_budget and self.state.get('initial_budget_verified')==0 and 0<=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(prior_budget)).total_seconds()<30*60
  if not reusable:
   if self.budget()!=0:raise ValueError('Draft already has funds; no duplicate deposit')
   self.state.update(initial_budget_verified=0,initial_budget_verified_at=stamp());self.save()
  wanted={r['nm']:r['article']for r in self.item['skus']}
  cached=stock_cache(self.db,self.item)
  if cached:products,observed,stock_source=cached
  else:
   source=self.wb.read('seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products','POST',body={'selectedPeriod':{'start':'2026-11-09','end':'2026-11-22'},'pastPeriod':{'start':'2026-10-26','end':'2026-11-08'},'nmIds':sorted(wanted),'skipDeletedNm':False,'limit':1000,'offset':0})
   products={r['product']['nmId']:r['product']for r in source['data']['products']};observed=stamp();stock_source='live_WB_read'
  if set(products)!=set(wanted)or any(p.get('vendorCode')!=wanted[n]or p.get('subjectId')!=50 or p.get('stocks',{}).get('wb',0)<1 or p.get('feedbackRating',0)<4.5 for n,p in products.items()):raise ValueError('Fresh SKU identity, available WB stock or rating changed; no funding')
  self.state.update(stock_readback={str(n):p for n,p in products.items()},stock_observed_at=observed,stock_source=stock_source,stock_validated_at=stamp());self.save()
  value=self.call('/api/advert/v1/bids/min','POST',{'advert_id':self.item['campaign_id'],'nm_ids':sorted(r['nm']for r in self.item['skus']),'payment_type':'cpc','placement_types':['search']})
  bids=parse_bids(value,self.item);self.state['minimum_bids']={str(k):v for k,v in bids.items()};self.save()
  body={'bids':[{'advert_id':self.item['campaign_id'],'nm_bids':[{'nm_id':n,'bid_kopecks':v,'placement':'search'}for n,v in sorted(bids.items())]}]}
  self.call('/api/advert/v1/bids','PATCH',body,step='bids')
  validate_campaign(self.campaign(),self.item,{4},bids)
  self.state.update(settings_verified=True,settings_verified_at=stamp());self.save()
 def fund(self):
  wallet=self.call('/adv/v1/balance')
  if wallet.get('currency')!=self.item['currency']or wallet.get('net',0)<1000:raise ValueError('Insufficient native WB balance; no card charge')
  if self.state.get('initial_budget_verified')!=0 or not self.state.get('settings_verified'):raise ValueError('Not a verified empty draft; no deposit')
  amount=1000
  try:receipt=self.call('/adv/v1/budget/deposit','POST',{'sum':1000,'type':1,'return':True},{'id':self.item['campaign_id']},step='deposit1000')
  except Rejected as exc:
   if not minimum_rejection(exc):raise
   # A definitive HTTP400 minimum-amount rejection transferred no funds.
   # Never apply this branch to a timeout, 429, 5xx, or ambiguous success.
   if wallet.get('net',0)<2000:raise ValueError('Insufficient WB balance for approved fallback')
   self.state['fallback_minimum_rejection_verified']=True;self.save();amount=2000
   receipt=self.call('/adv/v1/budget/deposit','POST',{'sum':2000,'type':1,'return':True},{'id':self.item['campaign_id']},step='deposit2000')
  # The documented return=true response is an authoritative updated budget,
  # avoiding another quota-heavy budget read for the same transaction.
  actual=receipt.get('total')if isinstance(receipt,dict)else None
  if type(actual)is not int:actual=self.budget()
  if actual!=amount:raise RuntimeError('Funding readback differs; no activation')
  self.state.update(funding_verified=True,budget=amount,funding_readback=receipt,funding_verified_at=stamp());self.save()
 def start(self):
  self.call('/adv/v0/start',params={'id':self.item['campaign_id']},step='start')
  inventory=self.call('/adv/v1/promotion/count')
  matches=[g['status']for g in inventory.get('adverts',[])for r in g.get('advert_list',[])if r['advertId']==self.item['campaign_id']]
  if matches!=[9]:raise ValueError('Activation status not verified')
  self.state.update(status='active_verified',activated_at=stamp(),final_inventory_status=9,auto_topup=False,model_calls=0);self.save()
def run():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':raise PermissionError('Public main only')
 db=State();auth=db.get(ROOT+':launch_authorization')or{};validate_authorization(auth);clients=[]
 for item in auth['items']:
  draft=db.get(ROOT+':draft:'+item['cabinet'])or{}
  if draft.get('campaign_id')!=item['campaign_id']or draft.get('steps',{}).get('create',{}).get('status')!='accepted':raise PermissionError('Accepted owned draft missing')
  prior=db.get(ROOT+':launch:'+item['cabinet'])or{}
  if prior.get('steps')!={}or prior.get('authorization_sha256')!=digest(auth):raise PermissionError('Prior attempt must have zero write calls and identical approval')
  superseded=db.get(ROOT+':launch_v2:'+item['cabinet'])or{}
  if superseded.get('steps')!={}or superseded.get('authorization_sha256')!=digest(auth):raise PermissionError('Superseded waiting attempt must have zero writes')
  read_failure=db.get(ROOT+':launch_v3:'+item['cabinet'])or{}
  if read_failure.get('steps')!={}or read_failure.get('authorization_sha256')!=digest(auth)or read_failure.get('status')!='attention':raise PermissionError('Previous read-only failure not confirmed')
  key=ROOT+':launch_v4:'+item['cabinet'];state=dict(status='preparing',authorization_sha256=digest(auth),steps={},started_at=stamp(),model_calls=0,previous_failed_before_writes=ROOT+':launch_v3:'+item['cabinet'])
  if read_failure.get('initial_budget_verified')==0 and read_failure.get('initial_budget_verified_at'):
   state.update(initial_budget_verified=0,initial_budget_verified_at=read_failure['initial_budget_verified_at'])
  if not db.put(key,state,once=True):raise RuntimeError('Launch receipt already exists; inspect it before any continuation')
  clients.append(Client(db,auth,item,state,key))
 try:
  for c in clients:c.prepare()
  for c in clients:c.fund()
  for c in clients:c.start()
 except Exception as exc:
  for c in clients:
   if c.state.get('status')!='active_verified':c.state.update(status='attention',error=str(exc)if isinstance(exc,(RuntimeError,ValueError,PermissionError))else type(exc).__name__);c.save()
  raise
 for c in clients:print(json.dumps({'cabinet':c.item['cabinet'],'campaign_id':c.item['campaign_id'],'status':c.state['status'],'selected_count':len(c.item['skus']),'auto_topup':False,'model_calls':0}),flush=True)
def continue_known_rejection():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':raise PermissionError('Public main only')
 db=State();auth=db.get(ROOT+':launch_authorization')or{};validate_authorization(auth)
 states={item['cabinet']:db.get(ROOT+':launch_v4:'+item['cabinet'])or{}for item in auth['items']}
 for item in auth['items']:
  s=states[item['cabinet']]
  if s.get('authorization_sha256')!=digest(auth)or s.get('settings_verified')is not True:raise PermissionError('Identical verified launch scope required')
  if any(x.get('status')in('submitting','uncertain')for x in s['steps'].values()):raise PermissionError('Unresolved write; no continuation')
  if s['steps'].get('start'):raise PermissionError('Prior start must be reviewed, not repeated')
 ip=states['token_2'];ooo=states['token_1']
 if ip.get('funding_verified')is not True or ip.get('budget')!=1000 or ip['steps'].get('deposit1000',{}).get('status')!='accepted':raise PermissionError('Exact funded IP receipt missing')
 first=ooo['steps'].get('deposit1000',{});fallback=ooo['steps'].get('deposit2000',{})
 if first.get('status')!='rejected'or not minimum_rejection(Rejected(first.get('http_status'),first.get('detail')))or fallback.get('status')!='rejected'or fallback.get('http_status')!=429 or ooo.get('fallback_minimum_rejection_verified')is not True:raise PermissionError('Not the exact definitive minimum/429 rejection sequence')
 claim=ROOT+':continue_known429'
 if not db.put(claim,{'status':'running','authorization_sha256':digest(auth),'started_at':stamp()},once=True):raise RuntimeError('Continuation already claimed; inspect receipts')
 clients={i['cabinet']:Client(db,auth,i,states[i['cabinet']],ROOT+':launch_v4:'+i['cabinet'])for i in auth['items']}
 for c in clients.values():c.wb.identity();c.state['previous_error']=c.state.pop('error',None);c.state['status']='continuing';c.save()
 try:
  clients['token_2'].start()
  c=clients['token_1'];receipt=c.call('/adv/v1/budget/deposit','POST',{'sum':2000,'type':1,'return':True},{'id':c.item['campaign_id']},step='deposit2000')
  total=receipt.get('total')if isinstance(receipt,dict)else None
  if type(total)is not int:total=c.budget()
  if total!=2000:raise RuntimeError('OOO fallback funding differs; no activation')
  c.state.update(funding_verified=True,budget=2000,funding_readback=receipt,funding_verified_at=stamp());c.save();c.start()
 except Exception as exc:
  for c in clients.values():
   if c.state.get('status')!='active_verified':c.state.update(status='attention',error=str(exc)if isinstance(exc,(RuntimeError,ValueError,PermissionError))else type(exc).__name__);c.save()
  raise
 db.put(claim,{'status':'complete','completed_at':stamp(),'authorization_sha256':digest(auth)})
 print(json.dumps({'status':'both_active_verified','selected_count':24,'model_calls':0}))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--continue-known-rejection',action='store_true');args=p.parse_args()
 continue_known_rejection()if args.continue_known_rejection else run()
