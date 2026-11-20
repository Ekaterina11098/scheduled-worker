"""Repair only unsubmitted confirmed deposits; all other funding remains untouched."""
import copy,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_loss_execute import IO as OwnerIO
from china_loss_control import PLAN,APPROVAL,digest
from china_daily_report_validity import require
from china_owner_report20_contract import validate
from china_execution_notice import proven
ROOT='china_agent:owner_funding20_repair:v1'
EXEC='china_agent:daily_ad_execution:v2:daily-2026-11-20-owner-approved-r1-budgets-1-buttons-8af5bada06d3f3f510206096-5122667182'
class IO(AdvertisingIO,OwnerIO):pass
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=IO();authorization=io.get(ROOT+':authorization');assert authorization['status']=='approved'and authorization['owner_id']==5122667182
 assert authorization['amounts']=={'40933588':1400,'41325622':100}and authorization['telegram_send']is False
 if io.get(ROOT+':execution'):
  e=io.get(ROOT+':execution');assert e['status']=='verified','Existing recovery: inspect, never replay';print('Already verified');return
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or'';path=u.path
  if host=='api.telegram.org':assert path.rsplit('/',1)[-1]=='getChatMember','No Telegram writes'
  if 'openai'in host:raise ValueError('No model calls')
  if host.endswith('wildberries.ru'):
   allowed=m=='GET'and path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance','/api/v2/list/goods/filter')or m=='POST'and path in('/api/advert/v2/budget','/api/v3/stocks/2126188')
   if m=='POST'and path=='/adv/v1/budget/deposit':
    cid=u.query.removeprefix('id=');allowed=cid in authorization['amounts']and kw.get('json',{}).get('sum')==authorization['amounts'][cid]
   assert allowed,'Outside confirmed two-deposit repair'
  if host.endswith('moysklad.ru'):assert m=='GET','No stock changes'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 a=io.get(APPROVAL+'356');p=io.get(PLAN+a['plan_id']);io.validate_owner(a);require(io,p)
 assert p['plan_sha256']==a['plan_sha256']==digest(p['items']);io.daily_report_plan=p;io.daily_report_approval=a;io.daily_report_current_revalidation=True
 old=io.get(EXEC);items={i['id']:i for i in p['items']};byid={i['id']:i for i in old['items']}
 wanted={i['id']:i for i in p['items']if str(i['campaign_id'])in authorization['amounts']}
 assert len(wanted)==2
 for iid in wanted:
  s=byid[iid];assert s['status']=='blocked'and not s.get('request')and not s.get('steps')and not s.get('wb_writes'),'Previously submitted deposits must not be repeated'
 assert all(proven(items[s['id']],s)for s in old['items']if s['id']not in wanted),'Unexpected remaining unverified funding'
 e=dict(status='running',created_at=now(),items=[],authorization_key=ROOT+':authorization',wb_writes=0,telegram_calls=0,model_calls=0)
 assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 def req(path,method='GET',body=None):
  time.sleep(1.2);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50)
  r.raise_for_status();return r.json()if r.content else{}
 def campaign(cid):
  rows=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(rows)==1 and rows[0]['id']==cid;return rows[0]
 def budget(cid):
  rows=req('/api/advert/v2/budget','POST',dict(advertIds=[cid]))['adverts'];assert len(rows)==1 and rows[0]['advertId']==cid and rows[0]['currency']=='CNY';return rows[0]['total']
 try:
  cfg=req('/api/advert/v1/config');wallet=req('/adv/v1/balance');assert cfg['currency']==wallet['currency']=='CNY'
  total=sum(authorization['amounts'].values());source=0 if wallet.get('balance',0)>=total else 1 if wallet.get('net',0)>=total else None;assert source is not None,'Insufficient wallet for confirmed remaining deposits'
  for iid,item in wanted.items():
   require(io,p);cid=item['campaign_id'];before=campaign(cid);amount=item['amount_cny']
   state=dict(id=iid,campaign_id=cid,status='preflight',before=before);e['items'].append(state);save()
   state['fresh_economics']=validate(io,item,before);initial=budget(cid);state['before_budget']=initial;save()
   assert initial<=item['balance_before']+2,'Campaign already funded since report; reconcile instead of repeat'
   assert cfg['minTopUp']<=amount*100 and before['status']==9
   assert campaign(cid)==before,'Campaign changed before funding'
   state.update(status='submitting',request=dict(path='/adv/v1/budget/deposit?id='+str(cid),method='POST',body=dict(sum=amount,type=source)));save()
   try:state['response']=req(state['request']['path'],'POST',state['request']['body'])
   except Exception:state['status']='uncertain';e['status']='uncertain';save();raise
   state['status']='accepted';e['wb_writes']+=1;save()
   for _ in range(15):
    after=campaign(cid);cash=budget(cid)
    if after==before and cash>=initial+amount-2:break
    time.sleep(5)
   else:raise ValueError('Funding WB readback not verified')
   state.update(status='verified',after=after,after_budget=cash,verified_at=now());save()
   child=ROOT+':campaign:'+str(cid);assert io.create(child,copy.deepcopy(state))
   registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=child;io.put('china_agent:verified_campaign_state:v1',registry)
   original_state=copy.deepcopy(byid[iid]);byid[iid].update(copy.deepcopy(state),prior_preflight_failure=original_state,owner_recovery_receipt=child)
   old['items']=[byid[s['id']]for s in old['items']];old['owner_recovery_receipt']=ROOT+':execution';io.put(EXEC,copy.deepcopy(old))
  assert all(proven(items[s['id']],s)for s in old['items'])
  old.update(status='done',all_actions_wb_verified=True,reconciled_at=now());io.put(EXEC,old)
  e.update(status='verified',verified_at=now(),original_execution_key=EXEC,already_verified_other_fundings_not_repeated=True);save()
 except Exception as ex:
  e['status']='uncertain'if any(s['status']in('submitting','accepted','uncertain')for s in e['items'])else'blocked';e['reason']=str(ex)[:350];save();raise
 print(json.dumps(dict(status=e['status'],recovered=len(e['items']),wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()

