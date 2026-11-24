"""Resume only the owner's exact zero-write blocked addition using standard executor."""
import copy,json,os,requests
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_loss_execute import IO as OwnerIO
from china_daily_ad_actions import execute,EXEC
from china_advertising_full_growth import validate_addition
from china_loss_control import PLAN,APPROVAL,digest
ROOT='china_agent:owner_addition53_recovery:2026-11-24:v1'
PID='daily-2026-11-24-midday-ready-v2-drr-0-buttons-e86ad19cae6cb5941977696c-5122667182'
class IO(AdvertisingIO,OwnerIO):pass
def main():
 io=IO();root=io.get(ROOT)
 if root:
  if root.get('status')=='verified':print('Already verified; no replay');return
  raise ValueError('Existing recovery claim; inspect journal instead of replaying')
 p=io.get(PLAN+PID);a=io.get(APPROVAL+'372');e=io.get(EXEC+PID)
 assert a['plan_id']==PID and a['sender_id']==5122667182 and p['plan_sha256']==a['plan_sha256']==digest(p['items'])
 assert len(p['items'])==len(e['items'])==1 and e['wb_writes']==0
 item=p['items'][0];s=e['items'][0]
 assert (item['nm_id'],item['campaign_id'],item['target_minor'],item['placement'])==(1556488196,42068186,27,'search')
 assert s['status']=='blocked'and s['reason']=='Addition price/stock unknown or changed'and not s.get('request')and not s.get('bid_phase')
 orig=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  m=method.upper();u=urlparse(url);body=kw.get('json');host=u.hostname or''
  if host.endswith('wildberries.ru'):
   if m=='PATCH':
    assert (u.path=='/adv/v0/auction/nms'and body==dict(nms=[dict(advert_id=42068186,nms=dict(add=[1556488196],delete=[]))]))or(u.path=='/api/advert/v1/bids'and body==dict(bids=[dict(advert_id=42068186,nm_bids=[dict(nm_id=1556488196,placement='search',bid_kopecks=27)])]))
   elif m=='POST':assert u.path in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2126188')
   else:assert m=='GET'and u.path not in('/adv/v0/start','/adv/v0/stop','/adv/v0/pause')
  elif host=='api.telegram.org':assert u.path.rsplit('/',1)[-1]in('getChatMember','editMessageText','sendMessage')
  elif host.endswith('moysklad.ru'):assert m=='GET'
  else:assert host==urlparse(os.environ['SUPABASE_URL']).hostname
  return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 io.validate_owner(a)
 io.daily_report_current_revalidation=True
 from china_advertising_v2 import http
 cp=http(io,'/api/advert/v2/adverts?ids=42068186')['adverts'][0]
 current=validate_addition(io,item,cp)
 root=dict(status='preflight_verified',created_at=datetime.now(timezone.utc).isoformat(),before_execution=copy.deepcopy(e),current_evidence=current,owner_instruction='сделай все и исправь эакие ошибки в коде',scope=dict(nm_id=1556488196,campaign_id=42068186,target_minor=27),wb_writes=0)
 assert io.create(ROOT,root)
 # Preserve original plan/hash/confirmation. Only a proven unsubmitted blocked preflight is reset.
 s.clear();s.update(id=item['id'],status='preflight',owner_recovery_ref=ROOT,preflight_failures=[root['before_execution']['items'][0]])
 e['status']='running';io.put(EXEC+PID,e)
 result=execute(io,a,p)
 root.update(status='verified'if result['items'][0]['status']=='verified'else'needs_attention',execution_key=EXEC+PID,wb_writes=result['wb_writes'],completed_at=datetime.now(timezone.utc).isoformat())
 io.put(ROOT,root)
 assert root['status']=='verified'
 print(json.dumps(dict(status=root['status'],wb_writes=root['wb_writes'],margin_before_ads=current['expected_margin_before_ads_cny'],price=current['price_cny'],free_stock=current['stock_free'],published_stock=current['published_stock'])))
if __name__=='__main__':main()
