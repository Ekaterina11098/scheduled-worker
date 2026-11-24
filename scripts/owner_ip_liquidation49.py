"""Exact owner-authorized IP liquidation test. Private immutable scope, durable writes."""
import copy,datetime,hashlib,json,os,time,requests
from owner_ad_tests23 import State,ReadWB,stamp
ROOT='ip_agent:liquidation49:2026-11-24:v1'
HOST='advert-api.wildberries.ru'
def projection(c):
 return dict(id=c['id'],status=c['status'],currency=c['currency'],bid_type=c['bid_type'],settings=c['settings'],members={str(n['nm_id']):n['bids_kopecks'] for n in c['nm_settings']})
def validate(a):
 if a.get('status')!='approved' or a.get('owner_id')!=5122667182 or a.get('cabinet')!='token_2' or a.get('currency')!='RUB':raise PermissionError('Owner scope missing')
 if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(a['expires_at']):raise PermissionError('Authorization expired')
 if any(a.get(k)is not False for k in ('auto_topup','card_charge_allowed','telegram_sends','other_schedules')):raise PermissionError('Capability expansion')
 if [(g['group'],len(g['items']),g['budget'],g['existing_id'])for g in a['groups']]!=[('Noel',6,3000,None),('Спрос',30,6000,42139004),('Без заказов',13,2000,None)]:raise PermissionError('Group scope changed')
 items=[n for g in a['groups']for n in g['items']]
 if len({n['nm']for n in items})!=49 or {n['nm']for n in items}&set(a['excluded_risk']+a['no_fbo']):raise PermissionError('SKU overlap or excluded SKU')
 if any(n['bid_minor']not in (295,309)for n in items) or sum(n['bid_minor']==309 for n in items)!=2:raise PermissionError('Rate scope changed')
class Runner:
 def __init__(self):
  self.db=State();self.a=self.db.get(ROOT+':approval');validate(self.a)
  self.wb=ReadWB(self.db,'token_2');self.wb.identity();self.deadline=time.time()+150*60
  self.s={'status':'preflight','steps':{},'created':{},'model_calls':0,'telegram_sends':0,'wb_write_attempts':0,'started_at':stamp()}
 def save(self):self.db.put(ROOT+':execution',self.s)
 def guard(self):
  validate(self.a)
  if self.db.get(ROOT+':approval')!=self.a:raise PermissionError('Authorization changed')
 def call(self,path,method='GET',body=None,params=None,step=None,host=HOST):
  reads={('GET','/adv/v1/promotion/count'),('GET','/api/advert/v2/adverts'),('GET','/adv/v1/balance'),('POST','/api/advert/v2/budget'),('POST','/api/advert/v1/bids/min'),('POST','/api/analytics/v3/sales-funnel/products')}
  writes={('GET','/adv/v0/pause'),('GET','/adv/v0/start'),('POST','/adv/v2/seacat/save-ad'),('PATCH','/adv/v0/auction/nms'),('PATCH','/api/advert/v1/bids'),('POST','/adv/v1/budget/deposit')}
  if (method,path)not in (writes if step else reads):raise PermissionError('Endpoint outside scope')
  if host!=HOST and not(host=='seller-analytics-api.wildberries.ru'and path=='/api/analytics/v3/sales-funnel/products'and not step):raise PermissionError('Host outside scope')
  if step and step in self.s['steps']:raise RuntimeError('Write already journaled; no repeat')
  for attempt in range(3):
   self.guard();pk='wb-pause:'+hashlib.sha256((self.wb.token+host+path).encode()).hexdigest()
   until=float((self.db.get(pk)or{}).get('until',0))
   if until>self.deadline:raise RuntimeError('Cooldown exceeds run; pending retained')
   while until>time.time():
    self.s.update(status='waiting_provider',waiting_path=path,resume_after=datetime.datetime.fromtimestamp(until,datetime.timezone.utc).isoformat());self.save();self.guard();time.sleep(min(25,max(.1,until-time.time())))
   if step:
    self.s['steps'][step]={'status':'submitting','method':method,'path':path,'body':body,'params':params,'at':stamp()};self.s['wb_write_attempts']+=1;self.save()
   try:r=requests.request(method,'https://'+host+path,headers={'Authorization':self.wb.token},params=params,json=body,timeout=(10,65),allow_redirects=False)
   except requests.RequestException:
    if step:self.s['steps'][step]['status']='uncertain';self.save()
    raise RuntimeError('Unknown request result; no replay')from None
   try:result=r.json()if r.content else{}
   except ValueError:result={'unparseable':True}
   raw=r.headers.get('X-Ratelimit-Retry')or r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Reset')
   try:delay=float(raw or 0)
   except ValueError:delay=0
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if r.status_code==429 or r.headers.get('X-Ratelimit-Remaining')=='0':self.db.put(pk,{'until':time.time()+max(3,delay)+5,'basis':'provider_header'})
   if r.status_code==429:
    if step:
     self.s.setdefault('definite_429',[]).append(copy.deepcopy(dict(self.s['steps'][step],status='rejected429',detail=result)))
     del self.s['steps'][step];self.save()
    continue
   if not r.ok or result.get('unparseable')if isinstance(result,dict)else not r.ok:
    if step:self.s['steps'][step].update(status='uncertain'if r.status_code>=500 or r.ok else'rejected',http=r.status_code,response=result);self.save()
    raise RuntimeError('API HTTP '+str(r.status_code)+' '+path)
   if step:self.s['steps'][step].update(status='accepted',response=result,accepted_at=stamp());self.save()
   return result
  raise RuntimeError('Provider rejection after bounded retries')
 def configs(self,ids):
  out={}
  for start in range(0,len(ids),50):
   rs=self.call('/api/advert/v2/adverts',params={'ids':','.join(map(str,ids[start:start+50]))})['adverts'];out.update({str(c['id']):c for c in rs})
  if set(out)!=set(map(str,ids)):raise ValueError('Configuration incomplete')
  return out
 def budgets(self,ids):
  rows=self.call('/api/advert/v2/budget','POST',{'advertIds':ids})['adverts']
  if {r['advertId']for r in rows}!=set(ids)or any(r['currency']!='RUB'or type(r['total'])is not int for r in rows):raise ValueError('Budget coverage/currency')
  return {str(r['advertId']):r['total']for r in rows}
 def run(self):
  if self.db.get(ROOT+':execution'):raise RuntimeError('Existing execution; inspect receipts instead of replay')
  if not self.db.put(ROOT+':execution',self.s,once=True):raise RuntimeError('Execution claimed')
  try:self.execute()
  except Exception as e:self.s.update(status='attention',error=str(e)if isinstance(e,(RuntimeError,PermissionError,ValueError))else type(e).__name__);self.save()
  self.s['finished_at']=stamp();self.save();print(json.dumps({'status':self.s['status'],'writes':self.s['wb_write_attempts'],'telegram_sends':0}),flush=True)
 def execute(self):
  index=self.call('/adv/v1/promotion/count');ids=sorted({r['advertId']for g in index.get('adverts',[])if g['status']in(4,9,11)for r in g.get('advert_list',[])})
  if 42139004 not in ids or len(ids)>50:raise ValueError('Existing campaign scope changed')
  before=self.configs(ids);self.s.update(before=before,baseline_at=stamp());self.save()
  target=before['42139004']
  if target['currency']!='RUB'or target['bid_type']!='manual'or target['settings']['payment_type']!='cpc'or target['settings']['placements']!={'search':True,'recommendations':False}:raise ValueError('Existing target changed')
  names={c['settings']['name']for c in before.values()}
  if any(g['name']in names for g in self.a['groups']if g['name']):raise ValueError('Named draft exists without execution receipt')
  wanted={n['nm']:n for g in self.a['groups']for n in g['items']}
  stock=self.call('/api/analytics/v3/sales-funnel/products','POST',{'selectedPeriod':{'start':'2026-11-23','end':'2026-11-23'},'pastPeriod':{'start':'2026-11-22','end':'2026-11-22'},'nmIds':sorted(wanted),'skipDeletedNm':False,'limit':1000,'offset':0},host='seller-analytics-api.wildberries.ru')
  products={r['product']['nmId']:r['product']for r in stock['data']['products']}
  if set(products)!=set(wanted)or any(p['vendorCode'].casefold()!=wanted[n]['article'].casefold()or p['subjectId']!=50 for n,p in products.items()):raise ValueError('SKU identity mismatch')
  eligible={n for n,p in products.items()if p.get('stocks',{}).get('wb',0)>0};self.s.update(stock_readback=products,stock_at=stamp(),zero_stock_skipped=sorted(set(wanted)-eligible));self.save()
  groups=copy.deepcopy(self.a['groups'])
  for g in groups:g['items']=[n for n in g['items']if n['nm']in eligible]
  if any(not g['items']for g in groups):raise ValueError('An entire group has no FBO')
  for cid,c in before.items():
   if c['status']==9 and cid!='42139004' and {n['nm_id']for n in c['nm_settings']}&eligible:raise ValueError('Active overlap in campaign '+cid+'; no changes')
  old={n['nm_id']:n for n in target['nm_settings']};current=groups[1];newn={n['nm']for n in groups[0]['items']+groups[2]['items']};deletes=sorted(set(old)&(newn|set(self.a['excluded_risk'])))
  adds=sorted({n['nm']for n in current['items']}-set(old))
  if (adds or deletes)and not target.get('restrictions',{}).get('can_change_nms'):raise ValueError('Existing campaign membership locked')
  if len(set(old)-set(deletes)|set(adds))>50:raise ValueError('Existing capacity exceeded')
  self.s['outside_scope_preserved']=sorted(set(old)-set(wanted)-set(self.a['excluded_risk']));self.save()
  minimum=self.call('/api/advert/v1/bids/min','POST',{'advert_id':42139004,'nm_ids':[next(iter(old))],'payment_type':'cpc','placement_types':['search']})
  bs=[b for n in minimum['bids']for b in n['bids']if b['type']=='search'and b['currency']=='RUB']
  if len(bs)!=1 or bs[0]['value']>295:raise ValueError('Category minimum above approved rate')
  self.s['minimum_receipt']=minimum
  wallet=self.call('/adv/v1/balance');self.s['wallet_before']=wallet
  budget=self.budgets([42139004]);self.s['budget_before']=budget
  needed=5000+max(0,6000-budget['42139004'])
  if wallet.get('currency')!='RUB'or wallet.get('net',0)<needed:raise ValueError('WB available net balance insufficient; no card charge')
  self.s.update(status='preflight_verified',groups=groups,maximum_deposit=needed);self.save()
  for g in groups:
   if g['existing_id']:continue
   body={'name':g['name'],'nms':[n['nm']for n in g['items']],'bid_type':'manual','payment_type':'cpc','placement_types':['search']}
   value=self.call('/adv/v2/seacat/save-ad','POST',body,step='create_'+g['group'])
   cid=value if type(value)is int else value.get('advertId')
   if type(cid)is not int or cid<=0:raise RuntimeError('Creation ID uncertain; no recreation')
   g['existing_id']=cid;self.s['created'][g['group']]=cid;self.save()
  if target['status']==9:self.call('/adv/v0/pause',params={'id':42139004},step='pause_existing')
  if adds or deletes:self.call('/adv/v0/auction/nms','PATCH',{'nms':[{'advert_id':42139004,'nms':{'add':adds,'delete':deletes}}]},step='membership_existing')
  bidrows=[{'advert_id':g['existing_id'],'nm_bids':[{'nm_id':n['nm'],'placement':'search','bid_kopecks':n['bid_minor']}for n in g['items']]}for g in groups]
  self.call('/api/advert/v1/bids','PATCH',{'bids':bidrows},step='bids_all')
  expected=copy.deepcopy(before)
  expected['42139004']['status']=11
  expected['42139004']['nm_settings']=[n for n in expected['42139004']['nm_settings']if n['nm_id']not in deletes]
  for nm in adds:expected['42139004']['nm_settings'].append({'nm_id':nm,'bids_kopecks':{'search':wanted[nm]['bid_minor'],'recommendations':0}})
  for n in expected['42139004']['nm_settings']:
   if n['nm_id']in {r['nm']for r in current['items']}:n['bids_kopecks']['search']=wanted[n['nm_id']]['bid_minor']
  allids=sorted(set(ids)|set(self.s['created'].values()));configured=self.configs(allids);self.s['configured_readback']=configured;self.save()
  for cid,c in expected.items():
   if projection(c)!=projection(configured[cid]):raise ValueError('Unapproved configuration variance '+cid)
  for g in groups:
   c=configured[str(g['existing_id'])]
   members={n['nm_id']:n['bids_kopecks']['search']for n in c['nm_settings']}
   if not g['group']=='Спрос'and set(members)!={n['nm']for n in g['items']}:raise ValueError('New campaign composition mismatch')
   if c['currency']!='RUB'or c['bid_type']!='manual'or c['settings']['payment_type']!='cpc'or c['settings']['placements']!={'search':True,'recommendations':False}or any(members.get(n['nm'])!=n['bid_minor']for n in g['items']):raise ValueError('Target bid/placement mismatch')
  balances=self.budgets([g['existing_id']for g in groups]);self.s['funding_before']=balances;self.save()
  for g in groups:
   cid=g['existing_id'];oldbal=balances[str(cid)]
   if g['group']!='Спрос'and oldbal!=0:raise ValueError('New draft already funded')
   amount=max(0,g['budget']-oldbal)
   if amount:self.call('/adv/v1/budget/deposit','POST',{'sum':amount,'type':1,'return':True},{'id':cid},step='deposit_'+g['group'])
  funded=self.budgets([g['existing_id']for g in groups]);self.s['funded_readback']=funded;self.save()
  if any(funded[str(g['existing_id'])]<g['budget']for g in groups):raise ValueError('Funding not confirmed')
  for g in groups:self.call('/adv/v0/start',params={'id':g['existing_id']},step='start_'+g['group'])
  after=self.configs(allids);self.s.update(after=after,readback_at=stamp());self.save()
  for cid,c in expected.items():
   if cid=='42139004':c['status']=9
   if projection(c)!=projection(after[cid]):raise ValueError('Final unexpected change '+cid)
  results=[]
  for g in groups:
   c=after[str(g['existing_id'])];members={n['nm_id']:n['bids_kopecks']['search']for n in c['nm_settings']}
   if c['status']!=9:raise ValueError('Campaign not active')
   for n in g['items']:
    if members.get(n['nm'])!=n['bid_minor']:raise ValueError('Final target missing')
    results.append(dict(n,campaign=g['existing_id'],status='verified'))
  self.s.update(status='verified',results=results,groups=groups,finished_at=stamp());self.save()
if __name__=='__main__':Runner().run()

