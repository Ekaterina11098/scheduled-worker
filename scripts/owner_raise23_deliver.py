import json,hashlib,uuid,requests,os
from datetime import datetime,timedelta,timezone,date
from types import SimpleNamespace
from urllib.parse import urlencode,urlparse,quote
from zoneinfo import ZoneInfo
from decimal import Decimal
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache
from china_price_delivery import deliver,rows
from china_price_buttons import prepare
from china_price_current_check import check
from china_agent.buyer_price_forecast import load,forecast
ROOT='china_agent:owner_raise_two_delivery:2026-11-23:v1'
def main():
 io=AdvertisingIO();c=Cache();now=datetime.now(ZoneInfo('Europe/Moscow'));day=now.date();assert str(day)=='2026-11-23'
 old=c.get(ROOT)
 if old:
  if old.get('status')=='sent':print('Already delivered');return
  raise RuntimeError('Existing recovery claim needs inspection; no replay')
 assert c.create(ROOT,dict(status='preparing',started_at=now.isoformat(),wb_writes=0))
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.telegram.org'and m=='POST'and u.path.rsplit('/',1)[-1]in('getMe','sendMessage'))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='api.moysklad.ru'and m=='GET')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and u.path=='/api/v3/stocks/2126188')
  assert ok,'Only two proposal delivery and scoped reads permitted';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 w=SimpleNamespace(day=day,now=now,chat=-1004342917488,mode='owner-raise23',delivery_mode='owner-raise23',get=io.get,audit={},original_http=original,uncertain=False,telegram_cooldown=0)
 def db(method,table,params=None,body=None,prefer=None):return io.db(table+('?' + urlencode(params)if params else ''),method,body,prefer)
 w.db=db
 cfg=db('GET','business_agent_config',dict(agent_id='eq.china',active='eq.true',limit=2));assert len(cfg)==1 and cfg[0]['chat_id']==w.chat
 basis=load(w);blocks=[]
 for nm,article,oldp,newp in [('1473243913','61-NoelBag-beige','208','218.5'),('1535337773','5-FurPanama-beige','111','117')]:
  before=forecast(basis,nm,article,oldp,oldp,day);after=forecast(basis,nm,article,oldp,newp,day);assert before and after,'Exact buyer forecast missing'
  blocks.append('Повышение · '+article+' Продавец: '+oldp.replace('.',',')+' → '+newp.replace('.',',')+' ¥\nПокупатель: '+f'{before:,}'.replace(',',' ')+' → '+f'{after:,}'.replace(',',' ')+' ₽')
 answer='\n\n'.join(blocks);checked=check(w,answer);assert checked==answer and len(rows(checked))==2,'Current facts no longer support exact two offers'
 update=-98320261123;prior=db('GET','business_agent_jobs',dict(agent_id='eq.china',update_id='eq.'+str(update),limit=2));assert not prior,'Existing recovery job'
 lease=str(uuid.uuid4());job=db('POST','business_agent_jobs',body=dict(agent_id='china',update_id=update,chat_id=w.chat,sender_id=5122667182,request_text='/china_owner_raise_two23',status='running',attempts=1,lease_token=lease,lease_until=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),answer=answer,tool_trace=[dict(name='china_price_daily_report',report_date=str(day),source_key='china_agent:owner_raise_review:2026-11-23:v1',execution_authorized=False)]),prefer='return=representation');assert len(job)==1;w.job=job[0]
 def patch(body):
  result=io.db('business_agent_jobs?id=eq.'+str(w.job['id'])+'&lease_token=eq.'+lease,'PATCH',body,'return=representation')
  if len(result)==1:w.job=result[0]
  return result
 w.patch=patch
 sha=hashlib.sha256(answer.encode()).hexdigest();expiry=datetime.combine(day+timedelta(days=1),datetime.min.time(),now.tzinfo).isoformat();markup,registry=prepare(answer,rows(answer),w.job['id'],str(day),expiry)
 key='china_agent:price_delivery:v2:'+str(day)+':owner-raise23'
 assert c.create(key+':prepared',dict(status='prepared',answer_sha256=sha,answer=answer,parts=[dict(method='sendMessage',text=answer)],selection_count=2,expires_at=expiry,execution_authorized=False,wb_writes=0,reply_markup=markup,button_registry=registry))
 c.put(ROOT,dict(status='prepared',job_id=w.job['id'],answer_sha256=sha,check=w.audit,wb_writes=0))
 deliver(w)
 receipt=c.get(key);assert receipt.get('status')=='sent'and receipt.get('message_ids')
 c.put(ROOT,dict(receipt,source_key=key,actual_delivery_at=datetime.now(timezone.utc).isoformat(),wb_writes=0));print(json.dumps(dict(status='sent',message_ids=receipt['message_ids'],job_id=w.job['id'],wb_writes=0)))
if __name__=='__main__':main()

