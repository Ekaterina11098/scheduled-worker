"""Exact owner-approved three additions. No budget/status/old-action writes."""
import sys,copy,json,hashlib,time,datetime,requests
sys.path.insert(0,'scripts')
from owner_ad_tests23 import State,ReadWB,stamp
ROOT='ip_agent:growth_add3:2026-11-27:v1';HOST='advert-api.wildberries.ru'
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def project(cs):
 return {cid:{k:c[k]for k in('id','status','currency','bid_type','settings','restrictions')}|{'members':{str(n['nm_id']):n for n in c['nm_settings']}}for cid,c in cs.items()}
def economics(a,price):
 # Conditional successful buyout; not expected profit and not a buyout forecast.
 # Own cost and dated commission/logistics; 3% acquiring and two logistic legs
 # are explicit stress assumptions, not asserted current fees/return probability.
 if price<=0 or a['own_cost']<=0 or not 0<a['commission_pct']<100:raise ValueError('Invalid economic base')
 commission=price*a['commission_pct']/100;tax=price*.15;acquiring=price*.03;logistics=2*a['logistics_rub'];storage=3*a['storage_day_rub'];ads=price*.05
 after=price-commission-tax-acquiring-logistics-storage-a['own_cost']-ads
 return dict(scenario='conditional_successful_buyout_stress_not_expected_profit',price=price,own_cost=a['own_cost'],commission_pct=a['commission_pct'],commission=commission,tax_reserve=tax,acquiring_assumption_pct=3,acquiring=acquiring,logistics_assumption_legs=2,logistics=logistics,storage_assumption_days=3,storage=storage,ad_at_target5pct=ads,conditional_after_ads=round(after,2),required_ad_conversion_pct=a['target_bid_kopecks']/100/ads*100,returns_probability=None,not_current_profit=True)
class Run:
 def __init__(self):
  self.db=State();self.a=self.db.get(ROOT+':approval');self.wb=ReadWB(self.db,'token_2');self.deadline=time.time()+4*3600;self.s=dict(status='preflight',writes={},wb_write_attempts=0,telegram_calls=0,started_at=stamp())
 def save(self):self.db.put(ROOT+':execution',self.s)
 def guard(self):
  if not self.a or self.a.get('status')!='approved' or self.a.get('cabinet')!='token_2' or len(self.a.get('items',[]))!=3 or digest(self.a['items'])!='dc1cbd5b62fa68db57ff6a58824e874801bb192a4f09b51b09cdb92c5a240510':raise PermissionError('Exact three-item approval required')
  if self.db.get(ROOT+':approval')!=self.a or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(self.a['expires_at']):raise PermissionError('Approval changed or expired')
  if any(self.a.get(k)is not False for k in('topup','pause_start','other_writes','telegram')):raise PermissionError('Scope expansion')
 def call(self,path,method='GET',body=None,params=None,host=HOST,step=None):
  allowed={('GET',HOST,'/adv/v1/promotion/count'),('GET',HOST,'/api/advert/v2/adverts'),('POST',HOST,'/api/advert/v1/bids/min'),('POST','seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products'),('GET','discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter'),('PATCH',HOST,'/adv/v0/auction/nms'),('PATCH',HOST,'/api/advert/v1/bids')}
  if(method,host,path)not in allowed:raise PermissionError('Endpoint boundary')
  write=method=='PATCH'
  if write and(step not in('membership','bids')or body!=self.s['planned_writes'].get(step)):raise PermissionError('Exact write body mismatch')
  key='wb-pause:'+hashlib.sha256((self.wb.token+host+path).encode()).hexdigest()
  for attempt in range(3):
   self.guard();until=float((self.db.get(key)or{}).get('until',0))
   if until>self.deadline:raise RuntimeError('Cooldown exceeds bounded execution')
   while until>time.time():
    self.s.update(status='waiting_provider',wait_endpoint=path,resume_after=datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat());self.save();time.sleep(min(25,max(.1,until-time.time())));self.guard()
   if write:
    if self.s['writes'].get(step,{}).get('status')in('submitting','accepted','uncertain'):raise RuntimeError('Existing write result, no replay')
    self.s['writes'][step]=dict(status='submitting',body=body,at=stamp());self.s['wb_write_attempts']+=1;self.save()
   try:r=requests.request(method,'https://'+host+path,headers={'Authorization':self.wb.token},params=params,json=body,timeout=(10,70),allow_redirects=False)
   except requests.RequestException:
    if write:self.s['writes'][step]['status']='uncertain';self.save()
    raise RuntimeError('Unknown request result, never replay')from None
   try:data=r.json()if r.content else{}
   except ValueError:data={'unparseable':True}
   raw=r.headers.get('X-Ratelimit-Retry')or r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Reset')
   try:delay=float(raw or 0)
   except ValueError:delay=0
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0':self.db.put(key,dict(until=time.time()+max(3,delay)+5,basis='provider_header'))
   if r.status_code==429:
    self.s.setdefault('definite429',[]).append(dict(path=path,at=stamp(),retry_after=delay))
    if write:self.s['writes'][step].update(status='rejected429',http=429)
    self.save();continue
   if not r.ok or isinstance(data,dict)and data.get('unparseable'):
    self.s['last_error']=dict(path=path,http=r.status_code,response=data)
    if write:self.s['writes'][step].update(status='uncertain'if r.status_code>=500 or r.ok else'rejected',http=r.status_code)
    self.save();raise RuntimeError('WB HTTP'+str(r.status_code)+' '+path)
   if write:self.s['writes'][step].update(status='accepted',accepted_at=stamp(),response=data);self.save()
   return data
  raise RuntimeError('Bounded429retries exhausted')
 def configs(self,ids):
  cs=self.call('/api/advert/v2/adverts',params={'ids':','.join(map(str,ids))})['adverts']
  if {c['id']for c in cs}!=set(ids):raise ValueError('Incomplete WB readback')
  return {str(c['id']):c for c in cs}
 def execute(self):
  self.guard();self.wb.identity();items=self.a['items'];wanted={a['nm']:a for a in items}
  self.s.update(prices={},economics={},minimum_receipts={});self.save()
  for a in items:
   d=self.call('/api/v2/list/goods/filter',params={'limit':1,'offset':0,'filterNmID':a['nm']},host='discounts-prices-api.wildberries.ru')
   rows=d['data']['listGoods']
   if len(rows)!=1 or rows[0]['nmID']!=a['nm']or rows[0].get('vendorCode','').casefold()!=a['sku'].casefold()or rows[0].get('currencyIsoCode4217')!='RUB':raise ValueError('Price identity/currency')
   sizes=rows[0].get('sizes')or[];prices=[r.get('discountedPrice')for r in sizes]
   if not prices or any(type(p)not in(int,float)or p<=0 for p in prices):raise ValueError('Current price missing')
   observed=min(prices);club=rows[0].get('clubDiscount')or 0
   if type(club)not in(int,float)or not 0<=club<100:raise ValueError('Invalid club discount')
   effective=min(a['saved_price'],observed*(1-club/100));scenario=economics(a,effective)
   self.s['prices'][str(a['nm'])]=dict(data=rows[0],observed_at=stamp(),calculation_price=effective);self.s['economics'][str(a['nm'])]=scenario;self.save()
   if scenario['conditional_after_ads']<=0:raise ValueError('Stress scenario does not support target DRR')
   time.sleep(.7)
  # Read minima BEFORE the final configuration so provider waits cannot stale a write baseline.
  for cid in sorted({a['campaign']for a in items}):
   a=next(a for a in items if a['campaign']==cid);place='recommendation'if a['placement']=='recommendations'else'search'
   m=self.call('/api/advert/v1/bids/min','POST',{'advert_id':cid,'nm_ids':[a['representative']],'payment_type':'cpc','placement_types':[place]})
   values=[b['value']for r in m.get('bids',[])if r.get('nm_id')==a['representative']for b in r.get('bids',[])if b.get('type')==place and b.get('currency')=='RUB']
   if len(values)!=1 or type(values[0])is not int or not 0<values[0]<=a['target_bid_kopecks']:raise ValueError('Minimum exceeds approved rate')
   self.s['minimum_receipts'][str(cid)]=dict(data=m,observed_at=stamp());self.save()
  inv=self.call('/adv/v1/promotion/count');ids=sorted({r['advertId']for g in inv.get('adverts',[])if g['status']==9 for r in g.get('advert_list',[])})
  if not ids or len(ids)>20 or not {a['campaign']for a in items}.issubset(ids):raise ValueError('Active scope bounds')
  stock=self.call('/api/analytics/v3/sales-funnel/products','POST',{'selectedPeriod':{'start':'2026-11-27','end':'2026-11-27'},'pastPeriod':{'start':'2026-11-26','end':'2026-11-26'},'nmIds':sorted(wanted),'skipDeletedNm':False,'limit':1000,'offset':0},host='seller-analytics-api.wildberries.ru')
  products={r['product']['nmId']:r['product']for r in stock['data']['products']}
  if set(products)!=set(wanted)or any(p['vendorCode'].casefold()!=wanted[nm]['sku'].casefold()or p['subjectId']!=50 or not p.get('stocks',{}).get('wb',0)>0 for nm,p in products.items()):raise ValueError('Current FBO/SKU/subject not confirmed')
  self.s.update(stock_readback=products,stock_observed_at=stamp());self.save()
  before=self.configs(ids);self.s.update(before=before,configuration_observed_at=stamp());self.save();expected=copy.deepcopy(before);groups={};bids={}
  for a in items:
   cid=str(a['campaign']);c=before[cid];place=a['placement'];placements={'search':place=='search','recommendations':place=='recommendations'}
   if c['status']!=9 or c['currency']!='RUB'or c['bid_type']!='manual'or c['settings']['payment_type']!='cpc'or c['settings']['placements']!=placements or not c['restrictions'].get('can_change_nms'):raise ValueError('Target configuration changed')
   if not any(n['nm_id']==a['representative']and n['subject']['id']==50 for n in c['nm_settings']):raise ValueError('Minimum representative subject changed')
   if any(n['nm_id']==a['nm']for v in before.values()for n in v['nm_settings']):raise ValueError('SKU already active, no duplicate addition')
   groups.setdefault(a['campaign'],[]).append(a['nm']);bid=dict(nm_id=a['nm'],placement=place,bid_kopecks=a['target_bid_kopecks']);bids.setdefault(a['campaign'],[]).append(bid)
   nm_bids={'search':0,'recommendations':0};nm_bids[place]=a['target_bid_kopecks'];expected[cid]['nm_settings'].append(dict(nm_id=a['nm'],subject={'id':50,'name':'сумки'},bids_kopecks=nm_bids))
  if any(len(c['nm_settings'])>50 for c in expected.values()):raise ValueError('Capacity exceeded')
  membership={'nms':[dict(advert_id=cid,nms={'add':sorted(nms),'delete':[]})for cid,nms in sorted(groups.items())]};bidbody={'bids':[dict(advert_id=cid,nm_bids=nms)for cid,nms in sorted(bids.items())]}
  self.s.update(planned_writes={'membership':membership,'bids':bidbody},expected=expected);self.save();self.guard()
  response=self.call('/adv/v0/auction/nms','PATCH',membership,step='membership')
  actual={r['advert_id']:r.get('nms',{}).get('added',[])for r in response.get('nms',[])}
  if {k:set(v)for k,v in actual.items()}!={k:set(v)for k,v in groups.items()}:raise ValueError('Membership response differs; no bid writes')
  time.sleep(3);self.call('/api/advert/v1/bids','PATCH',bidbody,step='bids');time.sleep(6)
  after=self.configs(ids);self.s.update(after=after,readback_at=stamp());self.save()
  if project(after)!=project(expected):raise ValueError('Final full active-scope readback differs; no replay')
  self.s.update(status='verified_all3',verified_count=3,other_settings_unchanged=True);self.save()
  self.db.put(ROOT+':approval',dict(self.a,status='fulfilled',execution_key=ROOT+':execution',verified_at=self.s['readback_at']))
  scope=[dict(kind='add',campaign=a['campaign'],nm=a['nm'],sku=a['sku'],placement=a['placement'],target_bid_minor=a['target_bid_kopecks'])for a in items]
  self.db.put(ROOT+':reporting-approval',dict(actions=scope,reporting_only=True,wb_authority=False))
  registry=self.db.get('advertising:ip:execution-registry:v1')or{'records':[]}
  if not any(r.get('execution_key')==ROOT+':execution'for r in registry.get('records',[])):registry.setdefault('records',[]).append(dict(approval_key=ROOT+':reporting-approval',execution_key=ROOT+':execution',show_recent=True));self.db.put('advertising:ip:execution-registry:v1',registry)
  for a in scope:self.db.put('advertising:ip:action-once:v1:'+digest({k:a.get(k)for k in('campaign','nm','kind','placement','stored_bid_minor','target_bid_minor')}),dict(status='verified',execution_key=ROOT+':execution',readback_at=self.s['readback_at']))
 def run(self):
  if self.db.get(ROOT+':execution'):raise RuntimeError('Existing execution, read instead of replay')
  if not self.db.put(ROOT+':execution',self.s,once=True):raise RuntimeError('Already claimed')
  try:self.execute()
  except Exception as e:self.s.update(status='attention',error=str(e)if isinstance(e,(PermissionError,ValueError,RuntimeError))else type(e).__name__)
  self.s['finished_at']=stamp();self.save();print(json.dumps({k:self.s.get(k)for k in('status','verified_count','wb_write_attempts','error')}))
  if self.s['status']!='verified_all3':raise SystemExit(1)
if __name__=='__main__':Run().run()
