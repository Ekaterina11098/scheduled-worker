"""Create/configure exact two-SKU search draft. No funding or start until amount agreed."""
import sys,json,copy,time,datetime,hashlib,requests
sys.path.insert(0,'scripts')
from owner_ad_tests23 import State,ReadWB,stamp
ROOT='ip_agent:manishki_search2:2026-11-27:v1';HOST='advert-api.wildberries.ru';SHA='935dd7299c1aee88c0ac5ebf11df535cda025b0d108c8c7205b2449bab6edc42'
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def project(c):return {k:c[k]for k in('advertId','status','currency','settings','restrictions')}|{'nms':sorted(c['nms'],key=lambda n:n['nmId'])}
class Runner:
 def __init__(self):
  self.db=State();self.a=self.db.get(ROOT+':approval');self.wb=ReadWB(self.db,'token_2');self.deadline=time.time()+4*3600;self.s=dict(status='preflight',steps={},wb_write_attempts=0,telegram_sends=0,created_id=None,started_at=stamp())
 def save(self):self.db.put(ROOT+':execution',self.s)
 def guard(self):
  if not self.a or digest(self.a)!=SHA or self.a.get('status')!='approved_create_configure':raise PermissionError('Exact owner-approved draft scope required')
  if self.db.get(ROOT+':approval')!=self.a or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(self.a['expires_at']):raise PermissionError('Approval changed/expired')
  if self.a['budget_deposit_authorized']or self.a['old_campaign_writes']or self.a['telegram']:raise PermissionError('Scope expansion')
 def call(self,path,method='GET',body=None,params=None,step=None):
  reads={('GET','/adv/v1/promotion/count'),('GET','/api/advert/v3/adverts'),('POST','/api/advert/v2/budget')};writes={('POST','/adv/v2/seacat/save-ad'),('PATCH','/api/advert/v1/bids')}
  if (method,path)not in(writes if step else reads):raise PermissionError('Endpoint boundary: no funding/start/status APIs')
  if step=='create'and body!=self.s.get('planned_create'):raise PermissionError('Create body mismatch')
  if step=='bids'and body!=self.s.get('planned_bids'):raise PermissionError('Bid body mismatch')
  key='wb-pause:'+hashlib.sha256((self.wb.token+HOST+path).encode()).hexdigest()
  for attempt in range(3):
   self.guard();until=float((self.db.get(key)or{}).get('until',0))
   if until>self.deadline:raise RuntimeError('Cooldown exceeds bounded execution')
   while until>time.time():
    self.s.update(status='waiting_provider',wait_endpoint=path,resume_after=datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat());self.save();time.sleep(min(25,max(.1,until-time.time())));self.guard()
   if step:
    if self.s['steps'].get(step,{}).get('status')in('submitting','accepted','uncertain'):raise RuntimeError('Write result exists, never replay')
    if step=='create'and time.time()-datetime.datetime.fromisoformat(self.s['stock_observed_at']).timestamp()>1800:raise ValueError('Stock preflight expired before creation')
    self.s['steps'][step]=dict(status='submitting',path=path,body=body,submitted_at=stamp());self.s['wb_write_attempts']+=1;self.save()
   try:r=requests.request(method,'https://'+HOST+path,headers={'Authorization':self.wb.token},params=params,json=body,timeout=(10,70),allow_redirects=False)
   except requests.RequestException:
    if step:self.s['steps'][step]['status']='uncertain';self.save()
    raise RuntimeError('Unknown request result; no recreation/replay')from None
   try:data=r.json()if r.content else{}
   except ValueError:data={'unparseable':True}
   raw=r.headers.get('X-Ratelimit-Retry')or r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Reset')
   try:delay=float(raw or 0)
   except ValueError:delay=0
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0':self.db.put(key,dict(until=time.time()+max(3,delay)+5,basis='provider_header'))
   if r.status_code==429:
    if step:self.s['steps'][step].update(status='rejected429',http=429)
    self.s.setdefault('definite429',[]).append(dict(path=path,retry_after=delay,at=stamp()));self.save();continue
   if not r.ok or isinstance(data,dict)and data.get('unparseable'):
    self.s['last_error']=dict(path=path,http=r.status_code,response=data)
    if step:self.s['steps'][step].update(status='uncertain'if r.status_code>=500 or r.ok else'rejected',http=r.status_code,response=data)
    self.save();raise RuntimeError('WB HTTP'+str(r.status_code)+' '+path)
   if step:self.s['steps'][step].update(status='accepted',response=data,accepted_at=stamp());self.save()
   return data
  raise RuntimeError('Bounded429retries exhausted')
 def configs(self,ids):
  d=self.call('/api/advert/v3/adverts',params={'advertIds':','.join(map(str,sorted(ids)))})
  if d.get('next')or {c['advertId']for c in d['adverts']}!=set(ids):raise ValueError('Configuration coverage')
  return {str(c['advertId']):c for c in d['adverts']}
 def verify_new(self,c,require_rate=True):
  if c['status']not in(4,11)or c['currency']!='RUB'or c['settings']!={'name':self.a['name'],'placements':['search'],'paymentType':'cpc'}:raise ValueError('New draft is not exact search-only CPC configuration')
  if {n['nmId']for n in c['nms']}!={a['nm']for a in self.a['items']}or any(n['subject']['id']!=756 for n in c['nms']):raise ValueError('New membership/category mismatch')
  if require_rate and any(n['bids']!=[{'type':'search','value':175}]for n in c['nms']):raise ValueError('Exact175search bids not verified')
 def execute(self):
  self.guard();self.wb.identity();p=self.db.get('ip_agent:manishki_review:2026-11-27:v1')or{}
  if p.get('status')!='complete'or time.time()-datetime.datetime.fromisoformat(p['stock']['observed_at']).timestamp()>1800:raise ValueError('Recent verified stock/configuration review required')
  wanted={a['nm']:a for a in self.a['items']};products={r['product']['nmId']:r['product']for r in p['stock']['data']['data']['products']if r['product']['nmId']in wanted}
  if set(products)!=set(wanted)or any(v['vendorCode'].casefold()!=wanted[nm]['sku'].casefold()or v['subjectId']!=756 or not v['stocks']['wb']>0 for nm,v in products.items()):raise ValueError('FBO/SKU identity')
  before={str(c['advertId']):c for c in p['configs']['data']['adverts']}
  if any(n['nmId']in wanted for c in before.values()if c['status']==9 for n in c['nms']):raise ValueError('Existing active overlap')
  minimum=p['minimum'];values=[b['value']for n in minimum['data']['bids']for b in n['bids']if b['type']=='search'and b['currency']=='RUB']
  if values!=[175]or time.time()-datetime.datetime.fromisoformat(minimum['observed_at']).timestamp()>86400:raise ValueError('Verified same-category minimum missing')
  inv=self.call('/adv/v1/promotion/count');active={r['advertId']for g in inv.get('adverts',[])if g['status']==9 for r in g.get('advert_list',[])}
  if active!=set(p['active_ids'])or any(g['status']==4 and g.get('count',0)>0 for g in inv.get('adverts',[])):raise ValueError('Catalog changed or unreviewed draft exists')
  self.s.update(before=before,stock_readback=products,stock_observed_at=p['stock']['observed_at'],minimum_receipt=minimum,planned_create=dict(name=self.a['name'],nms=sorted(wanted),bid_type='manual',payment_type='cpc',placement_types=['search']));self.save()
  d=self.call('/adv/v2/seacat/save-ad','POST',self.s['planned_create'],step='create');cid=d if type(d)is int else d.get('advertId')
  if type(cid)is not int or cid<=0:raise RuntimeError('Unknown creation ID; no recreation')
  self.s.update(created_id=cid,status='created_pending_readback');self.save();ids=set(map(int,before))|{cid};after=self.configs(ids);c=after[str(cid)];self.verify_new(c,False)
  self.s.update(configured=after,configuration_observed_at=stamp());self.save()
  if any(n['bids']!=[{'type':'search','value':175}]for n in c['nms']):
   # Solely new campaign, solely the approved two bids. No placement/status changes.
   self.s['planned_bids']={'bids':[{'advert_id':cid,'nm_bids':[{'nm_id':a['nm'],'placement':'search','bid_kopecks':175}for a in self.a['items']]}]};self.save();self.call('/api/advert/v1/bids','PATCH',self.s['planned_bids'],step='bids');after=self.configs(ids);c=after[str(cid)];self.verify_new(c)
  self.verify_new(c)
  budget=self.call('/api/advert/v2/budget','POST',{'advertIds':[cid]})
  b=budget['adverts']
  if len(b)!=1 or b[0]['advertId']!=cid or b[0]['currency']!='RUB':raise ValueError('New budget readback mismatch')
  self.s.update(after=after,readback_at=stamp(),new_budget=budget,new_budget_observed_at=stamp(),status='configured_waiting_budget_amount',verified_items=2,old_campaign_unchanged=project(before['40192945'])==project(after['40192945']),other_campaign_differences=[k for k in before if project(before[k])!=project(after[k])],funding_requests=0,start_requests=0);self.save()
 def run(self):
  if self.db.get(ROOT+':execution'):raise RuntimeError('Existing execution; inspect instead of replay')
  if not self.db.put(ROOT+':execution',self.s,once=True):raise RuntimeError('Already claimed')
  try:self.execute()
  except Exception as e:self.s.update(status='attention',error=str(e)if isinstance(e,(PermissionError,ValueError,RuntimeError))else type(e).__name__)
  self.s['finished_at']=stamp();self.save();print(json.dumps({k:self.s.get(k)for k in('status','created_id','verified_items','error','wb_write_attempts')}))
  if self.s['status']!='configured_waiting_budget_amount':raise SystemExit(1)
if __name__=='__main__':Runner().run()
