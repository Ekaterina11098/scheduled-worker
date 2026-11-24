import json,hashlib,uuid,requests,os,copy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from urllib.parse import urlencode,urlparse
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache
from china_price_delivery import deliver,rows
from china_price_buttons import prepare
from china_price_current_check import check
from china_agent.buyer_price_forecast import load,forecast
ROOT='china_agent:owner_price_report_two:2026-11-24:v1'
DEL='china_agent:price_delivery:v2:2026-11-24:morning'
OLDHASH='928335a17498cd76bba7b20cf3aca272c516854acf75ae22c115c12e3619773a'
def main():
 io=AdvertisingIO();c=Cache();now=datetime.now(ZoneInfo('Europe/Moscow'));day=now.date();assert str(day)=='2026-11-24'
 if c.get(ROOT):
  print(json.dumps({'status':c.get(ROOT).get('status'),'note':'existing claim; never resend'}));return
 assert c.create(ROOT,dict(status='preparing',started_at=now.isoformat(),wb_writes=0,model_calls=0))
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.telegram.org'and m=='POST'and u.path.rsplit('/',1)[-1]in('getMe','sendMessage'))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='api.moysklad.ru'and m=='GET')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and u.path=='/api/v3/stocks/2126188')
  assert ok,'Price proposals only; WB mutations forbidden';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 w=SimpleNamespace(day=day,now=now,chat=-1004342917488,mode='morning',delivery_mode='morning',get=io.get,audit={},original_http=original,uncertain=False,telegram_cooldown=0)
 def db(method,table,params=None,body=None,prefer=None):return io.db(table+('?' +urlencode(params)if params else ''),method,body,prefer)
 w.db=db
 assert c.get(DEL)is None and c.get(DEL+':part:0')is None,'Already attempted delivery; no replay'
 prepared=c.get(DEL+':prepared');assert prepared['answer_sha256']==OLDHASH and prepared['selection_count']==0
 job=db('GET','business_agent_jobs',dict(id='eq.368'));assert len(job)==1
 job=job[0];assert job['status']=='running'and job['answer']==prepared['answer']
 basis=load(w);blocks=[]
 for nm,article,oldp,newp in [('1473243914','043-NoelBag-brown','208','218.5'),('1473243891','0-NoelBag-green','175','179')]:
  before=forecast(basis,nm,article,oldp,oldp,day);after=forecast(basis,nm,article,oldp,newp,day);assert before and after,'Buyer forecast missing'
  blocks.append('Повышение · '+article+' Продавец: '+oldp.replace('.',',')+' → '+newp.replace('.',',')+' ¥\nПокупатель: '+f'{before:,}'.replace(',',' ')+' → '+f'{after:,}'.replace(',',' ')+' ₽')
 # Preserve the prepared report lower-data status; do not turn missing data into no candidates.
 answer='\n\n'.join(blocks+['Снижение: нет данных'])
 assert check(w,answer)==answer and len(rows(answer))==2,'Exact current preflight failed'
 sha=hashlib.sha256(answer.encode()).hexdigest();expiry=prepared['expires_at'];markup,registry=prepare(answer,rows(answer),368,str(day),expiry)
 revised=dict(status='prepared',answer_sha256=sha,answer=answer,parts=[dict(method='sendMessage',text=answer)],selection_count=2,expires_at=expiry,execution_authorized=False,wb_writes=0,reply_markup=markup,button_registry=registry)
 # Original failed scheduled run45348475433 never reached Telegram. Preserve its frozen revision.
 assert c.create(DEL+':revision:unsent:'+OLDHASH,dict(prepared,revision_reason='owner explicitly included two reviewed proposals before first send'))
 lease=str(uuid.uuid4());claimed=io.db('business_agent_jobs?id=eq.368&status=eq.running&lease_token=eq.'+job['lease_token'],'PATCH',dict(lease_token=lease,lease_until=(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat(),answer=answer),'return=representation')
 assert len(claimed)==1,'Existing report lease changed; stop'
 w.job=claimed[0]
 def patch(body):
  result=io.db('business_agent_jobs?id=eq.368&lease_token=eq.'+lease,'PATCH',body,'return=representation')
  if len(result)==1:w.job=result[0]
  return result
 w.patch=patch
 assert c.get(DEL)is None and c.get(DEL+':part:0')is None
 c.put(DEL+':prepared',revised)
 c.put(ROOT,dict(status='prepared',job_id=368,answer_sha256=sha,preflight=w.audit,wb_writes=0,model_calls=0))
 deliver(w)
 receipt=c.get(DEL);assert receipt['status']=='sent'and receipt['job_id']==368 and receipt['answer_sha256']==sha
 for mid,key in zip(receipt['message_ids'],receipt['receipt_keys']):
  binding=c.get('china_agent:price_report_message:v1:'+str(mid));sent=c.get(key)
  assert binding['report_sha256']==sha and binding['report_job_id']==368 and binding['receipt_key']==key and sent['status']=='sent'and sent['receipt']['chat']['id']==w.chat
 c.put('china_agent:scheduled_price_release:2026-11-24:morning',dict(status='sent',job_id=368,target_at='2026-11-24T10:30:00+03:00',actual_sent_at=receipt['completed_at'],message_ids=receipt['message_ids'],recovery_key=ROOT,wb_writes=0,model_calls=0))
 c.put(ROOT,dict(receipt,bindings_verified=True,source_key=DEL,wb_writes=0,model_calls=0))
 print(json.dumps({'status':'sent','job_id':368,'message_ids':receipt['message_ids'],'bindings_verified':True,'answer':answer,'wb_writes':0}))
if __name__=='__main__':main()
