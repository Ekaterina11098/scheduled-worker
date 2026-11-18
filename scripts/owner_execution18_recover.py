"""Read-only advertising reconciliation; resume only the exact confirmed unsubmitted450."""
import copy,json,requests,time
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_loss_control import PLAN,APPROVAL
from china_daily_ad_actions import execute,execution_order
from china_package_readback import validate
from china_execution_notice import proven,deliver_result
from china_confirmed_report_recovery import register_campaigns
ROOT='china_agent:owner_execution18_reconcile:v1'
ADS='daily-2026-11-18-owner-review18-r3-drr-0-buttons-d320db1e7225965af79b9278-5122667182'
BUD='daily-2026-11-18-owner-review18-r3-budgets-1-buttons-2c5dad30dfb8236e766abf02-5122667182'
io=AdvertisingIO();assert not io.get(ROOT+':recovery'),'No automatic repeat of recovery'
assert io.create(ROOT+':recovery',dict(status='running',created_at=datetime.now(timezone.utc).isoformat(),allowed_deposit_cny=450))
original=requests.sessions.Session.request;deposits=[]
def guard(session,method,url,*args,**kw):
 u=urlparse(url);m=method.upper();path=u.path
 if u.hostname==urlparse(io.url).hostname:ok=path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
 elif u.hostname=='advert-api.wildberries.ru':
  ok=(m=='GET'and path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/balance'))or(m=='POST'and path in('/api/advert/v2/budget','/api/advert/v1/bids/min'))
  if m=='POST'and path=='/adv/v1/budget/deposit':
   body=kw.get('json')or{};ok=u.query=='id=40933588'and body.get('sum')==450 and not deposits
   if ok:deposits.append(dict(at=datetime.now(timezone.utc).isoformat(),amount_cny=450))
 elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and path=='/api/v2/list/goods/filter'
 elif u.hostname=='api.moysklad.ru':ok=m=='GET'and path.startswith('/api/remap/1.2/')
 elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and path.startswith('/api/v3/stocks/')
 elif u.hostname=='api.telegram.org':ok=m=='POST'and path.rsplit('/',1)[-1]in('sendMessage','editMessageText')
 else:ok=False
 assert ok,'Recovery forbids unrelated transport '+m+' '+str(u.hostname)+path
 return original(session,method,url,*args,**kw)
requests.sessions.Session.request=guard
try:
 p=io.get(PLAN+ADS);e=io.get('china_agent:daily_ad_execution:v2:'+ADS);a=io.get(APPROVAL+'345')
 assert a['sender_id']==5122667182 and a['plan_id']==ADS and a['plan_sha256']==p['plan_sha256']
 assert io.create(ROOT+':ads_before',e)
 def campaign(cid):
  r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params=dict(ids=str(cid)),headers={'Authorization':io.token},timeout=50);r.raise_for_status();rows=r.json()['adverts'];assert len(rows)==1 and rows[0]['id']==cid and rows[0]['currency']=='CNY';return rows[0]
 result=validate(execution_order(p['items']),e['items'],campaign)
 assert result['status']=='verified'
 assert all(proven(i,next(s for s in e['items']if s['id']==i['id']))for i in p['items'])
 e.update(package_readback=result,status='done',completed_at=datetime.now(timezone.utc).isoformat(),reconciled_by=ROOT)
 io.put('china_agent:daily_ad_execution:v2:'+ADS,e);register_campaigns(io,p,e);deliver_result(io,a,p,e)
 bp=io.get(PLAN+BUD);be=io.get('china_agent:daily_ad_execution:v2:'+BUD);ba=io.get(APPROVAL+'346')
 assert ba['sender_id']==5122667182 and ba['plan_id']==BUD and ba['plan_sha256']==bp['plan_sha256']
 target=next(i for i in bp['items']if i['id']=='topup:40933588');assert target['amount_cny']==450
 blocked=next(s for s in be['items']if s['id']==target['id'])
 assert blocked['status']=='blocked'and blocked['reason']=='Companion campaign changes not all WB verified'and not blocked.get('request')and not blocked.get('submitted_at')and not blocked.get('before_budget')
 assert io.create(ROOT+':budgets_before',be)
 be.setdefault('blocked_recovery_audit',[]).append(copy.deepcopy(blocked));be['items']=[s for s in be['items']if s['id']!=blocked['id']]
 io.put('china_agent:daily_ad_execution:v2:'+BUD,be)
 outcome=execute(io,ba,bp)
 state=next(s for s in outcome['items']if s['id']==target['id'])
 status='verified'if proven(target,state)else'attention'
 io.put(ROOT+':recovery',dict(status=status,ads_verified=17,advertising_writes=0,deposits=deposits,budget_item_status=state['status'],before_budget=state.get('before_budget'),after_budget=state.get('after_budget'),completed_at=datetime.now(timezone.utc).isoformat()))
 print(json.dumps(dict(status=status,advertising_writes=0,deposits=len(deposits))))
except Exception as ex:
 import traceback
 io.put(ROOT+':recovery',dict(status='attention',error=str(ex),trace=traceback.format_exc(),deposits=deposits))
 raise
finally:requests.sessions.Session.request=original
