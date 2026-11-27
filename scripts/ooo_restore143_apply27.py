"""Exact private owner-approved additions; no funding, status changes or Telegram."""
import copy,datetime,hashlib,json,os,time,requests
from ooo_report_executor import DB as BaseDB,Executor,Stop,Deferred,project,stamp
from ooo_composition_review import observe
TASK='ooo_agent:restore143:2026-11-27:v1'
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class DB(BaseDB):
 def allowed(self,key):
  if key.startswith(TASK+':')or key=='ooo_agent:campaign_composition:v1:42217557':return
  super().allowed(key)
def scope(auth,state,method,path,body,params):
 cid=auth['campaign']
 if (method,path)==('GET','/api/advert/v2/adverts')and params=={'ids':str(cid)}:return
 if (method,path)==('PATCH','/adv/v0/auction/nms')and body=={'nms':[{'advert_id':cid,'nms':{'add':state['add_nm_ids'],'delete':[]}}]}:return
 if (method,path)==('PATCH','/api/advert/v1/bids')and body=={'bids':[{'advert_id':cid,'nm_bids':state['bid_changes']}]}:return
 raise Stop('Request outside exact additions authorization')
def run():
 db=DB();auth=db.get(TASK+':authorization')or{}
 if auth.get('status')!='approved'or auth.get('cabinet')!='token_1'or auth.get('currency')!='KGS'or auth.get('campaign')!=42217557 or auth.get('recommendations_minor')!=325 or auth.get('additional_topup_kgs')!=0 or auth.get('telegram_allowed')is not False or len(set(auth.get('add_nm_ids',[])))!=1:raise Stop('Exact single-SKU authorization required')
 state=db.get(TASK+':execution')
 if state and state.get('status')=='verified':print('Already verified; no replay');return
 if state and state.get('status')=='attention':raise Stop('Existing attention retained')
 if not state:
  state={'status':'preflight','steps':{},'started_at':stamp(),'run_id':os.environ['GITHUB_RUN_ID'],'authorization_sha256':digest(auth),'telegram_calls':0,'model_calls':0,'additional_topup_kgs':0};db.once(TASK+':execution',state)
 def save():
  state['wb_writes']=sum(v.get('status')=='accepted'for v in state['steps'].values());db.update(TASK+':execution',state)
 def guard():
  if db.get(TASK+':authorization')!=auth or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(auth['expires_at']):raise Stop('Approval changed or expired')
 def request(method,url,**kw):
  scope(auth,state,method,url.removeprefix('https://advert-api.wildberries.ru'),kw.get('json'),kw.get('params'))
  if method=='PATCH':guard()
  return requests.request(method,url,**kw)
 ex=Executor(db=db,token=os.environ['WB_TOKEN_1'],request=request);ex.identity();cid=auth['campaign'];deadline=time.time()+130*60
 while time.time()<deadline:
  try:
   if not state.get('before'):
    baseline=ex.configs(state,save,{cid})[str(cid)]
    if baseline.get('status')!=9 or baseline.get('currency')!='KGS'or baseline.get('settings',{}).get('placements')!={'search':False,'recommendations':True}or baseline.get('restrictions',{}).get('can_change_nms')is not True:raise Stop('Target configuration changed')
    adds=sorted(set(auth['add_nm_ids'])-{n['nm_id']for n in baseline['nm_settings']})
    bids=[{'nm_id':nm,'placement':'recommendations','bid_kopecks':325}for nm in auth['add_nm_ids'] if nm in adds or next(n for n in baseline['nm_settings']if n['nm_id']==nm)['bids_kopecks'].get('recommendations')!=325]
    expected=copy.deepcopy(baseline)
    for n in expected['nm_settings']:
     if n['nm_id']in auth['add_nm_ids']:n['bids_kopecks']['recommendations']=325
    state.update(before=baseline,expected={str(cid):expected},add_nm_ids=adds,bid_changes=bids,adds={str(cid):adds},bids={str(cid):bids});save()
   if state['add_nm_ids']:ex.call(state,save,'PATCH','/adv/v0/auction/nms',{'nms':[{'advert_id':cid,'nms':{'add':state['add_nm_ids'],'delete':[]}}]},step='memberships')
   if state['bid_changes']:ex.call(state,save,'PATCH','/api/advert/v1/bids',{'bids':[{'advert_id':cid,'nm_bids':state['bid_changes']}]},step='bids')
   after=ex.configs(state,save,{cid});ex.verify(state,after)
   state.update(after=after[str(cid)],status='verified',verified_at=stamp())
   for key in('safe_error','waiting_path','resume_after'):state.pop(key,None)
   save();key='ooo_agent:campaign_composition:v1:'+str(cid);db.put(key,observe(db.get(key),after[str(cid)],state['verified_at']))
   print('Exact additions and recommendations bids verified; no funding/status/Telegram calls');return
  except Deferred:
   state['status']='waiting_shared_quota';save();until=float(state.get('resume_after',0))
   if until<=time.time():until=time.time()+15
   while time.time()<until:
    if time.time()>=deadline:raise Stop('Window elapsed; receipts retained')
    time.sleep(min(30,max(.1,until-time.time())))
  except Exception as err:
   state.update(status='attention',safe_error=str(err)if isinstance(err,Stop)else type(err).__name__);save();raise
 raise Stop('Window elapsed; receipts retained')
if __name__=='__main__':run()
