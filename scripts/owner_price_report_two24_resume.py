import os,json,requests
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache
from china_price_delivery import deliver,rows
from china_agent.price_brief import plain_payload
ROOT='china_agent:owner_price_report_two:2026-11-24:v1'
DEL='china_agent:price_delivery:v2:2026-11-24:morning'
def main():
 io=AdvertisingIO();c=Cache();p=c.get(ROOT);assert p['status']=='prepared'
 if c.get(DEL):assert c.get(DEL)['status']=='sent';return
 assert c.get(DEL+':part:0')is None
 assert c.get(DEL+':part:0:failed_before_http:20261124T074358')['error']=="No module named 'china_agent.price_brief'"
 assert c.create(ROOT+':resume_pre_send',dict(status='claimed',wb_writes=0)),'Existing resume; no resend'
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.telegram.org'and m=='POST'and u.path.rsplit('/',1)[-1]in('getMe','sendMessage'))
  assert ok,'Delivery only';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 jobs=io.db('business_agent_jobs?id=eq.368','GET');assert len(jobs)==1
 job=jobs[0];pr=c.get(DEL+':prepared')
 assert job['status']=='running'and job['answer']==pr['answer']and pr['answer_sha256']==p['answer_sha256'] and len(rows(job['answer']))==2
 # Validate formatter before claiming a Telegram delivery part.
 plain_payload(job['answer'],io.get('china_agent:prices:v1'))
 now=datetime.now(ZoneInfo('Europe/Moscow'))
 w=SimpleNamespace(day=now.date(),now=now,chat=-1004342917488,mode='morning',delivery_mode='morning',get=io.get,job=job,audit={},original_http=original,uncertain=False,telegram_cooldown=0)
 def patch(body):
  r=io.db('business_agent_jobs?id=eq.368&lease_token=eq.'+job['lease_token'],'PATCH',body,'return=representation')
  if len(r)==1:w.job=r[0]
  return r
 w.patch=patch;deliver(w)
 r=c.get(DEL);assert r['status']=='sent'
 for mid,key in zip(r['message_ids'],r['receipt_keys']):
  b=c.get('china_agent:price_report_message:v1:'+str(mid));s=c.get(key)
  assert b['report_sha256']==pr['answer_sha256']and b['report_job_id']==368 and b['receipt_key']==key and s['receipt']['chat']['id']==w.chat and s['status']=='sent'
 registry=c.get(pr['button_registry']['key']);assert registry['status']=='active'and registry['report_job_id']==368 and registry['report_sha256']==pr['answer_sha256']
 c.put(ROOT,dict(r,source_key=DEL,bindings_verified=True,wb_writes=0,model_calls=0))
 c.put('china_agent:scheduled_price_release:2026-11-24:morning',dict(status='sent',job_id=368,target_at='2026-11-24T10:30:00+03:00',actual_sent_at=r['completed_at'],message_ids=r['message_ids'],recovery_key=ROOT,wb_writes=0,model_calls=0))
 print(json.dumps({'status':'sent','message_ids':r['message_ids'],'bindings_verified':True,'wb_writes':0}))
if __name__=='__main__':main()
