"""Exact208 result reconciliation; owner says finish confirmed report; never repeat other actions."""
import copy,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_loss_execute import IO as LossIO
from china_loss_control import PLAN
ROOT='china_agent:owner_reports21_fix208:v1'
def main():
 io=AdvertisingIO();a=io.get('china_agent:loss_plan_approval:v1:359');p=io.get(PLAN+a['plan_id'])
 assert a['sender_id']==5122667182 and p['parent_plan_id']=='daily-2026-11-21-drr-0'
 item=next(i for i in p['items']if i['id']=='40933588:1473244338')
 assert item['old_minor']==30 and item['target_minor']==32 and item['placement']=='recommendations'
 original=requests.sessions.Session.request;writes=0
 def guard(session,method,url,*args,**kw):
  nonlocal writes
  u=urlparse(url);host=u.hostname or'';m=method.upper()
  if 'openai'in host:raise ValueError('No model')
  if host=='api.telegram.org':assert u.path.endswith('/getChatMember'),'No Telegram sends'
  if host.endswith('wildberries.ru'):
   if m=='PATCH':
    expected=dict(bids=[dict(advert_id=40933588,nm_bids=[dict(nm_id=1473244338,placement='recommendations',bid_kopecks=32)])])
    assert u.path=='/api/advert/v1/bids'and kw.get('json')==expected and writes==0,'Only one exact corrective bid'
    writes+=1
   else:assert (m=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config','/api/v2/list/goods/filter'))or(m=='POST'and(u.path=='/api/advert/v1/bids/min'or u.path=='/api/v3/stocks/2126188')),'Only preflight reads'
  if host.endswith('moysklad.ru'):assert m=='GET'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def campaign():
  r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':40933588},headers={'Authorization':io.token},timeout=40);r.raise_for_status();return r.json()['adverts'][0]
 def bid(c):return next(n for n in c['nm_settings']if n['nm_id']==1473244338)['bids_kopecks']['recommendations']
 old=io.get(ROOT);reads=[]
 for _ in range(3):
  if reads:time.sleep(10)
  reads.append(campaign())
 baseline=reads[-1];vals=[bid(c)for c in reads]
 if vals==[32,32,32]:
  result=dict(status='verified',read_only=True,reads=reads,wb_writes=0,verified_at=datetime.now(timezone.utc).isoformat())
  io.put(ROOT,result)if old else io.create(ROOT,result);return
 if old:raise ValueError('Previous corrective journal exists; no repeat')
 assert vals==[30,30,30],'Bid not stable at old approved value'
 assert all(c['status']==9 and c['settings']==baseline['settings']and c['nm_settings']==baseline['nm_settings']for c in reads)
 LossIO.validate_owner(io,a)
 from china_advertising_growth import validate_raise
 io.daily_report_current_revalidation=True;validate_raise(io,item,baseline)
 q=requests.post('https://advert-api.wildberries.ru/api/advert/v1/bids/min',json=dict(advert_id=40933588,nm_ids=[1473244338],payment_type='cpc',placement_types=['recommendation']),headers={'Authorization':io.token},timeout=40);q.raise_for_status()
 values=[b['value']for n in q.json()['bids']if n['nm_id']==1473244338 for b in n['bids']if b['currency']=='CNY'and b['type']=='recommendation'];assert len(values)==1 and values[0]<=32
 body=dict(bids=[dict(advert_id=40933588,nm_bids=[dict(nm_id=1473244338,placement='recommendations',bid_kopecks=32)])])
 state=dict(status='submitting',before=baseline,stable_reads=reads,approved_item=item,approval_job=359,request=body,submitted_at=datetime.now(timezone.utc).isoformat(),wb_writes=0)
 assert io.create(ROOT,state)
 r=requests.patch('https://advert-api.wildberries.ru/api/advert/v1/bids',json=body,headers={'Authorization':io.token},timeout=40);r.raise_for_status()
 state.update(status='accepted',response=r.json()if r.content else{},wb_writes=writes);io.put(ROOT,state)
 final=[]
 for _ in range(3):
  time.sleep(12);final.append(campaign())
 expected=copy.deepcopy(baseline)
 next(n for n in expected['nm_settings']if n['nm_id']==1473244338)['bids_kopecks']['recommendations']=32
 ok=all(c['status']==expected['status']and c['settings']==expected['settings']and sorted(c['nm_settings'],key=lambda n:n['nm_id'])==sorted(expected['nm_settings'],key=lambda n:n['nm_id'])for c in final)
 state.update(status='verified'if ok else'uncertain',after=final[-1],final_reads=final,verified_at=datetime.now(timezone.utc).isoformat()if ok else None);io.put(ROOT,state)
 assert ok,'Corrective result not stable; no replay'
if __name__=='__main__':main()
