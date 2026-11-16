"""Resume only four preflight-only approved deposits; inventory all budgets afterwards."""
import copy,json,os
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qs
import requests
ROOT='china_agent:owner_funding_fix:2026-11-16:v1'
PID='daily-2026-11-16-budgets-1-buttons-989c2b630168b6cbb1d4dbd0-5122667182'
EXPECTED={40933588:1450,40945502:100,41298169:750,41325637:100}
def main():
 from china_advertising_state import AdvertisingIO
 from china_loss_execute import IO as OwnerIO
 from china_loss_control import PLAN,APPROVAL,digest
 from china_daily_ad_actions import process_and_deliver
 from china_execution_notice import proven
 from owner_budget_inventory16 import collect
 from china_cloud_cost_control import stamp
 class RecoveryIO(AdvertisingIO):
  validate_owner=OwnerIO.validate_owner
 io=RecoveryIO();p=io.get(PLAN+PID);a=io.get(APPROVAL+'334');key='china_agent:daily_ad_execution:v2:'+PID;e=io.get(key)
 assert a['sender_id']==5122667182 and a['plan_id']==PID and a['execution_key']==key
 assert p['plan_sha256']==a['plan_sha256']==digest(p['items'])=='0192b5ea281e2a78e2de23f98dbb29a3a64b544aa664d6945af478d065fb18fa'
 assert {i['campaign_id']:i['amount_cny']for i in p['items']}==EXPECTED|{41155909:100}
 assert all(i['kind']=='topup_campaign'for i in p['items'])
 io.validate_owner(a)
 audit=io.get(ROOT+':recovery')
 if audit:raise RuntimeError('Recovery already journalled; inspect states, never replay deposits')
 old={s['id']:s for s in e['items']};items={i['id']:i for i in p['items']}
 assert proven(items['topup:41155909'],old['topup:41155909'])
 blocked=[s for s in e['items']if s['id']!='topup:41155909']
 assert len(blocked)==4 and all(s['status']=='blocked'and s.get('reason')=='Composition changed outside the confirmed report pair'and not any(k in s for k in('request','response','submitted_at','before_budget'))for s in blocked)
 assert io.create(ROOT+':original_execution',e)
 assert io.create(ROOT+':completion_contract',dict(authorization_key=APPROVAL+'334',plan_id=PID,plan_sha256=p['plan_sha256'],execution_key=key,approval_job=334,completion_driver='china_daily_ad_actions.process_and_deliver',do_not_repeat=['topup:41155909'],allowed_remaining={str(k):v for k,v in EXPECTED.items()},registered_at=stamp()))
 assert io.create(ROOT+':recovery',dict(status='resuming_preflight_only',original_states=blocked,execution_key=key,created_at=stamp()))
 e=copy.deepcopy(e);e['items']=[old['topup:41155909']];e['status']='running';io.put(key,e)
 result=process_and_deliver(io,a,p)
 states={s['id']:s for s in result['items']}
 verified=[i for i in p['items']if proven(i,states[i['id']])]
 pending=[dict(id=i['id'],status=states[i['id']]['status'],reason=states[i['id']].get('reason'))for i in p['items']if not proven(i,states[i['id']])]
 assert states['topup:41155909']==old['topup:41155909'],'Already-verified deposit changed'
 current=collect(io,'after-recovery')
 delivery=io.get('china_agent:daily_ad_result:v2:'+PID+':verified')or{}
 out=dict(status='verified'if not pending else'partial',execution_key=key,verified_count=len(verified),newly_funded_cny=sum(i['amount_cny']for i in verified if i['campaign_id']in EXPECTED),previously_funded_cny=100,missing=pending,delivery_key='china_agent:daily_ad_result:v2:'+PID+':verified',delivery_status=delivery.get('status'),delivery_message_id=delivery.get('message_id'),completed_at=stamp(),all_campaign_audit_key=ROOT+':audit:after-recovery')
 io.put(ROOT+':recovery',out)
 if not pending:assert delivery.get('status')=='sent'and delivery.get('message_id'),'Final verified result receipt missing; do not replay WB'
 print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':
 original=requests.sessions.Session.request;deposited=set()
 def guard(self,method,url,*args,**kwargs):
  p=urlparse(url);host=p.hostname or'';path=p.path;method=method.upper()
  if host=='advert-api.wildberries.ru':
   if path=='/adv/v1/budget/deposit':
    cid=int(parse_qs(p.query)['id'][0]);body=kwargs.get('json')or{}
    assert method=='POST'and cid in EXPECTED and body.get('sum')==EXPECTED[cid]and cid not in deposited,'Unauthorized or duplicate deposit'
    deposited.add(cid)
   else:assert(path,method)in{('/adv/v1/promotion/count','GET'),('/api/advert/v2/adverts','GET'),('/api/advert/v2/budget','POST'),('/api/advert/v1/config','GET'),('/adv/v1/balance','GET')},'Unrelated WB action forbidden'
  elif host=='discounts-prices-api.wildberries.ru':assert method=='GET'and path=='/api/v2/list/goods/filter'
  elif host=='marketplace-api.wildberries.ru':assert method=='POST'and path=='/api/v3/stocks/2126188'
  elif host=='api.moysklad.ru':assert method=='GET'
  elif host=='api.telegram.org':assert path.rsplit('/',1)[-1]in('getMe','getChatMember','sendMessage')
  else:assert host==urlparse(os.environ['SUPABASE_URL']).hostname and path.startswith('/rest/v1/')
  return original(self,method,url,*args,**kwargs)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=original

