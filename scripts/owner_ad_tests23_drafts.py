"""Create only two explicitly scoped zero-budget drafts and read native quotes."""
import datetime,hashlib,json,os,time
from owner_ad_tests23 import ROOT,REPO,State,ReadWB,stamp
import requests
HOST='advert-api.wildberries.ru'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def validate(plan,item,pre):
 if plan.get('status')!='approved_draft_and_quote' or plan.get('owner_id')!=5122667182 or plan.get('max_new_campaigns')!=2 or len(plan.get('items',[]))!=2:raise PermissionError('Exact draft scope')
 if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(plan['expires_at']):raise PermissionError('Draft authorization expired')
 if item['cabinet']not in('token_1','token_2')or item['currency']!=('KGS'if item['cabinet']=='token_1'else'RUB'):raise PermissionError('Cabinet/currency')
 if item.get('auto_topup')is not False or item.get('payment_type')!='cpc'or item.get('bid_type')!='manual'or item.get('placements')!=['search']:raise PermissionError('Unexpected placement/payment')
 ids=[r['nm']for r in item['skus']]
 if len(set(ids))!=len(ids)or not 1<=len(ids)<=30 or any(type(n)is not int for n in ids):raise PermissionError('Exact nonempty unique SKU scope')
 if item['cabinet']=='token_2'and 1007948808 in ids or item['cabinet']=='token_1'and 851316021 in ids:raise PermissionError('Protected SKU')
 if pre.get('identity_verified')is not True or (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(pre['finished_at'])).total_seconds()>3600:raise PermissionError('Stale preflight')
 for k in ('funnel','prices','campaigns','wallet'):
  if pre['stages'].get(k,{}).get('status')!='complete':raise PermissionError('Required preflight unavailable: '+k)
 products={r['product']['nmId']:r['product']for r in pre['stages']['funnel']['data']['data']['products']}
 goods={r['nmID']:r for r in pre['stages']['prices']['data']}
 active={n['nm_id']for c in pre['stages']['campaigns']['data']if c['status']==9 for n in c['nm_settings']}
 for r in item['skus']:
  p=products.get(r['nm'],{});g=goods.get(r['nm'],{})
  if p.get('vendorCode')!=r['article']or g.get('vendorCode')!=r['article']or p.get('subjectId')!=50 or p.get('stocks',{}).get('wb',0)<3 or p.get('feedbackRating',0)<4.5:raise PermissionError('SKU identity, subject, rating or stock')
  if r['nm']in active:raise PermissionError('Already advertising')
 return ids
class Draft:
 def __init__(self,db,item,state,key):self.db=db;self.item=item;self.state=state;self.key=key;self.wb=ReadWB(db,item['cabinet'])
 def save(self):
  self.db.put(self.key,self.state)
  if self.db.get(self.key)!=self.state:raise RuntimeError('Journal readback mismatch')
 def call(self,path,method='GET',body=None,params=None,step=None):
  reads={('POST','/api/advert/v1/bids/min'),('POST','/api/advert/v2/budget'),('GET','/api/advert/v2/adverts'),('GET','/api/advert/v1/config')}
  if step:
   if step!='create' or (method,path)!=('POST','/adv/v2/seacat/save-ad')or body!={'name':self.item['name'],'nms':sorted(r['nm']for r in self.item['skus']),'bid_type':'manual','payment_type':'cpc','placement_types':['search']}:raise PermissionError('Only exact zero-budget draft creation is allowed')
   old=self.state['steps'].get(step)
   if old:
    if old['status']=='accepted':return old['response']
    raise RuntimeError('Prior creation unresolved or rejected; no replay')
  elif(method,path)not in reads:raise PermissionError('Not a draft read endpoint')
  pause='wb-pause:'+hashlib.sha256((self.wb.token+HOST+path).encode()).hexdigest()
  until=float((self.db.get(pause)or{}).get('until',0))
  if until>time.time():raise RuntimeError('Provider cooldown; no request sent')
  if step:
   self.state['steps'][step]={'status':'submitting','body':body,'submitted_at':stamp()};self.save()
  time.sleep(2)
  try:r=requests.request(method,'https://'+HOST+path,params=params,json=body,headers={'Authorization':self.wb.token},timeout=(10,65),allow_redirects=False)
  except requests.RequestException:
   if step:self.state['steps'][step]['status']='uncertain';self.save()
   raise RuntimeError('Transport outcome uncertain; no blind repeat')from None
  if r.status_code==429:
   try:delay=float(r.headers.get('Retry-After')or r.headers.get('X-Ratelimit-Retry')or 60)
   except ValueError:delay=60
   self.db.put(pause,dict(until=time.time()+max(60,delay)+3,basis='provider_header'))
  if not r.ok:
   try:error=r.json()
   except ValueError:error={'message':r.text[:1500]}
   # Keep provider diagnostics private; never log credentials.
   error=json.loads(json.dumps(error).replace(self.wb.token,'[redacted]'))
   self.state.setdefault('api_errors',[]).append(dict(path=path,http_status=r.status_code,error=error,observed_at=stamp()))
   if step:self.state['steps'][step].update(status='rejected',http_status=r.status_code)
   self.save();raise RuntimeError('WB HTTP '+str(r.status_code)+' '+path)
  try:value=r.json()if r.content else{}
  except ValueError:
   if step:self.state['steps'][step]['status']='uncertain';self.save()
   raise RuntimeError('Ambiguous provider response; no replay')from None
  if step:self.state['steps'][step].update(status='accepted',response=value,accepted_at=stamp());self.save()
  return value
 def prepare(self):
  self.wb.identity()
  body={'name':self.item['name'],'nms':sorted(r['nm']for r in self.item['skus']),'bid_type':'manual','payment_type':'cpc','placement_types':['search']}
  v=self.call('/adv/v2/seacat/save-ad','POST',body,step='create')
  cid=v if type(v)is int else v.get('advertId')if isinstance(v,dict)else None
  if type(cid)is not int or cid<=0:raise RuntimeError('Created ID unresolved; no replay')
  self.state['campaign_id']=cid;self.save()
  cs=self.call('/api/advert/v2/adverts',params={'ids':str(cid)})['adverts']
  if len(cs)!=1:raise ValueError('Draft readback incomplete')
  c=cs[0]
  if c['id']!=cid or c['status']!=4 or c.get('currency')!=self.item['currency']or c.get('bid_type')!='manual'or c['settings'].get('name')!=self.item['name']or c['settings'].get('payment_type')!='cpc'or c['settings'].get('placements')!={'search':True,'recommendations':False}or{n['nm_id']for n in c['nm_settings']}!=set(body['nms']):raise ValueError('Unexpected draft; no activation/funding')
  self.state['draft']=c;self.save()
  budgets=self.call('/api/advert/v2/budget','POST',{'advertIds':[cid]}).get('adverts',[])
  if len(budgets)!=1 or budgets[0].get('advertId')!=cid or budgets[0].get('currency')!=self.item['currency']or budgets[0].get('total')!=0:raise ValueError('Draft zero budget unconfirmed')
  self.state['zero_budget_verified_at']=stamp();self.save()
  self.state['minimum_bids']=self.call('/api/advert/v1/bids/min','POST',{'advert_id':cid,'nm_ids':body['nms'],'payment_type':'cpc','placement_types':['search']});self.save()
  try:self.state['config']=self.call('/api/advert/v1/config')
  except RuntimeError:self.state['config_unavailable']=True
  self.state.update(status='draft_quoted',finished_at=stamp(),money_transferred=0,wb_activation_calls=0);self.save()
def run():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':raise PermissionError('Public main only')
 db=State();plan=db.get(ROOT+':manifest')or{}
 for item in plan['items']:
  pre=db.get(ROOT+':preflight:'+item['cabinet'])or{};validate(plan,item,pre)
  key=ROOT+':draft:'+item['cabinet'];state={'status':'preparing','manifest_sha256':digest(plan),'steps':{},'created_at':stamp(),'money_transferred':0,'model_calls':0}
  if not db.put(key,state,once=True):print(json.dumps({'cabinet':item['cabinet'],'status':'prior_receipt_preserved'}));continue
  d=Draft(db,item,state,key)
  try:d.prepare()
  except Exception as e:state.update(status='attention',error=str(e)if isinstance(e,(RuntimeError,ValueError,PermissionError))else type(e).__name__);d.save()
  print(json.dumps({'cabinet':item['cabinet'],'status':state['status'],'money_transferred':0,'model_calls':0}))
def quote_existing():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':raise PermissionError('Public main only')
 db=State();plan=db.get(ROOT+':manifest')or{}
 for item in plan['items']:
  validate(plan,item,db.get(ROOT+':preflight:'+item['cabinet'])or{})
  key=ROOT+':draft:'+item['cabinet'];state=db.get(key)or{}
  if state.get('manifest_sha256')!=digest(plan)or state.get('steps',{}).get('create',{}).get('status')!='accepted' or type(state.get('campaign_id'))is not int:raise PermissionError('No exact accepted draft receipt')
  d=Draft(db,item,state,key);d.wb.identity();cid=state['campaign_id']
  for name,path,method,body in [
   ('budget_quote','/api/advert/v2/budget','POST',{'advertIds':[cid]}),
   ('minimum_bids','/api/advert/v1/bids/min','POST',{'advert_id':cid,'nm_ids':sorted(r['nm']for r in item['skus']),'payment_type':'cpc','placement_types':['search']}),
   ('config','/api/advert/v1/config','GET',None)]:
   if name in state:continue
   try:state[name]=d.call(path,method,body)
   except Exception as e:state.setdefault('quote_errors',{})[name]=str(e)if isinstance(e,(RuntimeError,ValueError,PermissionError))else type(e).__name__
   d.save()
  print(json.dumps({'cabinet':item['cabinet'],'status':'read_quotes_retained','money_transferred':0,'model_calls':0}))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--quote-existing',action='store_true');args=p.parse_args()
 quote_existing()if args.quote_existing else run()
