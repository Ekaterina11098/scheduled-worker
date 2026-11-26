"""One exact owner-approved composition/funding/resume package. No Telegram/models."""
import copy,datetime,hashlib,json,os,time
import requests
from ooo_report_executor import DB as BaseDB,Executor,Stop,Deferred,project,stamp,ROOT as COMMAND
from ooo_composition_review import observe
TASK='ooo_agent:potential_apply:2026-11-26:v1'
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class DB(BaseDB):
 def allowed(self,key):
  if key.startswith(TASK+':')or key=='ooo_agent:funding_review:2026-11-26:evidence'or key=='ooo_agent:midday:2026-11-26:1500:read'or key=='ooo_agent:campaign_composition:v1:42217183':return
  super().allowed(key)

def prepare(auth,baseline):
 cid=auth['campaign'];keep=set(auth['keep_nm_ids'])
 if len(keep)!=3 or auth.get('recommendations_minor')!=325 or auth.get('deposit_kgs')!=1200 or auth.get('resume')is not True:raise Stop('Exact three-SKU/325/1200/resume package required')
 if baseline.get('id')!=cid or baseline.get('status')not in(9,11)or baseline.get('currency')!='KGS'or baseline.get('bid_type')!='manual'or baseline.get('settings',{}).get('payment_type')!='cpc'or baseline['settings'].get('placements')!={'search':False,'recommendations':True}:raise Stop('Unsupported target baseline')
 ids={n['nm_id']for n in baseline['nm_settings']}
 if not keep<=ids or not baseline.get('restrictions',{}).get('can_change_nms'):raise Stop('Approved members unavailable')
 expected=copy.deepcopy(baseline);expected['status']=9
 expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']in keep]
 bids=[]
 for n in expected['nm_settings']:
  if n['bids_kopecks'].get('recommendations')!=325:bids.append({'nm_id':n['nm_id'],'placement':'recommendations','bid_kopecks':325})
  n['bids_kopecks']['recommendations']=325
 return expected,sorted(ids-keep),bids

def request_scope(auth,state,method,path,body,params):
 cid=auth['campaign']
 if method=='GET'and path=='/api/advert/v2/adverts':
  if set(map(int,(params or{}).get('ids','').split(',')))!=set(auth['readback_ids']):raise Stop('Read scope mismatch')
 elif method=='PATCH'and path=='/adv/v0/auction/nms':
  if body!={'nms':[{'advert_id':cid,'nms':{'add':[],'delete':state['delete_nm_ids']}}]}:raise Stop('Membership write outside authorization')
 elif method=='PATCH'and path=='/api/advert/v1/bids':
  if body!={'bids':[{'advert_id':cid,'nm_bids':state['bid_changes']}]}:raise Stop('Bid write outside authorization')
 elif method=='GET'and path in('/adv/v0/start','/adv/v0/pause'):
  if params!={'id':cid}:raise Stop('Status write outside authorization')
 elif method=='POST'and path=='/api/advert/v2/budget':
  if body!={'advertIds':[cid]}:raise Stop('Budget read outside authorization')
 elif method=='POST'and path=='/adv/v1/budget/deposit':
  if params!={'id':cid}or body.get('sum')!=1200 or body.get('type')not in(0,1)or body.get('return')is not True:raise Stop('Funding write outside authorization')
 elif method=='GET'and path in('/adv/v1/balance','/api/advert/v1/config'):pass
 else:raise Stop('Endpoint outside exact package')

def run():
 db=DB();auth=db.get(TASK+':authorization')or{}
 if auth.get('status')!='approved'or auth.get('cabinet')!='token_1'or auth.get('currency')!='KGS'or auth.get('telegram_allowed')is not False:raise Stop('Exact private owner authorization required')
 cid=auth['campaign'];state=db.get(TASK+':execution')
 if state and state.get('status')=='verified':print('Already verified; no repeat');return
 if state and state.get('status')=='attention':raise Stop('Existing attention retained; reconciliation required')
 if not state:
  state={'status':'preflight','steps':{},'started_at':stamp(),'run_id':os.environ['GITHUB_RUN_ID'],'authorization_sha256':digest(auth),'wb_writes':0,'telegram_calls':0,'model_calls':0};db.once(TASK+':execution',state)
 def save():
  state['wb_writes']=sum(v.get('status')=='accepted'for v in state.get('steps',{}).values())
  db.update(TASK+':execution',state)
 def guard():
  if db.get(TASK+':authorization')!=auth or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(auth['expires_at']):raise Stop('Authorization changed or expired')
 def request(method,url,**kwargs):
  path=url.removeprefix('https://advert-api.wildberries.ru');request_scope(auth,state,method,path,kwargs.get('json'),kwargs.get('params'))
  if method=='PATCH'or path in('/adv/v0/start','/adv/v0/pause','/adv/v1/budget/deposit'):guard()
  return requests.request(method,url,**kwargs)
 ex=Executor(db=db,token=os.environ['WB_TOKEN_1'],request=request);ex.identity()
 def call(method,path,body=None,params=None,step=None):return ex.call(state,save,method,path,body,params,step)
 deadline=time.time()+130*60
 while time.time()<deadline:
  try:
   if not state.get('before'):
    source=db.get(auth['baseline_source'])or{};snapshot=source.get('sources',{}).get('configurations',{})
    baseline=snapshot.get('data',{}).get(str(cid))
    if not baseline or digest(project(baseline))!=auth['baseline_sha256']:raise Stop('Verified baseline differs from authorization')
    age=time.time()-datetime.datetime.fromisoformat(snapshot['observed_at']).timestamp()
    if age<0 or age>1800:raise Stop('Baseline older than 30 minutes; fresh read required before writes')
    expected,deletes,bids=prepare(auth,baseline)
    state.update(before=baseline,baseline_observed_at=snapshot['observed_at'],baseline_source=auth['baseline_source'],expected={str(cid):expected},delete_nm_ids=deletes,bid_changes=bids,adds={},bids={str(cid):bids});save()
   if state['before']['status']==9:call('GET','/adv/v0/pause',params={'id':cid},step='pause_target')
   if state['delete_nm_ids']:call('PATCH','/adv/v0/auction/nms',{'nms':[{'advert_id':cid,'nms':{'add':[],'delete':state['delete_nm_ids']}}]},step='memberships')
   if state['bid_changes']:call('PATCH','/api/advert/v1/bids',{'bids':[{'advert_id':cid,'nm_bids':state['bid_changes']}]},step='bids')
   ex.fund(state,save,{'cid':cid,'amount_kgs':1200},'deposit_'+str(cid)+'_1200')
   if not state.get('funding_verified_at'):
    rows=call('POST','/api/advert/v2/budget',{'advertIds':[cid]})['adverts']
    prior=state['funding_before_by_campaign'][str(cid)]['total'];receipt=state['steps']['deposit_'+str(cid)+'_1200']['response']
    if len(rows)!=1 or rows[0].get('advertId')!=cid or rows[0].get('currency')!='KGS'or receipt.get('total')!=prior+1200 or rows[0].get('total')!=prior+1200:raise Stop('Accepted deposit requires reconciliation; never repeat')
    state.update(funding_after=rows[0],funding_verified_at=stamp());save()
   call('GET','/adv/v0/start',params={'id':cid},step='resume_target')
   after=ex.configs(state,save,set(auth['readback_ids']));ex.verify(state,{str(cid):after[str(cid)]})
   overlaps=[]
   for other,cfg in after.items():
    if int(other)==cid or cfg.get('status')!=9:continue
    for n in cfg.get('nm_settings',[]):
     if n['nm_id']in auth['keep_nm_ids']and cfg.get('settings',{}).get('placements',{}).get('recommendations'):overlaps.append({'cid':int(other),'nm':n['nm_id'],'placement':'recommendations','bid':n['bids_kopecks'].get('recommendations')})
   state.update(after=after[str(cid)],verified_at=stamp(),status='verified',overlaps_with_other_active_campaigns=overlaps)
   for key in('safe_error','waiting_path','resume_after'):state.pop(key,None)
   save()
   key='ooo_agent:campaign_composition:v1:'+str(cid);value=observe(db.get(key),after[str(cid)],state['verified_at'])
   db.put(key,value)
   print('Exact three-SKU package funded, resumed and verified; no Telegram/model calls');return
  except Deferred:
   state['status']='waiting_shared_quota';save()
   until=float(state.get('resume_after',0))
   if until<=time.time():until=time.time()+15
   while time.time()<until:
    if time.time()>=deadline:raise Stop('Job window elapsed; durable receipts retained')
    time.sleep(min(30,max(.1,until-time.time())))
  except Exception as error:
   state.update(status='attention',safe_error=str(error)if isinstance(error,Stop)else type(error).__name__);save();raise
 raise Stop('Job window elapsed; durable receipts retained')
if __name__=='__main__':run()
