"""Recover only verified-absent17Nov scheduled price report, no WB/model calls."""
import os,json,hashlib
import requests
from china_cloud_cost_control import Cache,stamp
ROOT='china_agent:price_delivery:v2:2026-11-17:intraday'
def main():
 c=Cache();scope=c.get(ROOT+':owner_recovery')
 assert scope and scope['status']=='authorized'and scope['visual_absence_verified']is True and scope['job_id']==343
 assert scope['chat_id']==-1004342917488 and scope['report_only']and scope['wb_writes']==0
 if (c.get(ROOT)or{}).get('status')=='sent':print('already_sent');return
 assert c.create(ROOT+':recovery_claim',dict(status='running',started_at=stamp())),'Existing recovery: inspect, no repeat'
 p=c.get(ROOT+':prepared');old=c.get(ROOT+':part:0')
 assert old['status']=='uncertain'and p['answer_sha256']==scope['answer_sha256']and p['selection_count']==0 and p['parts']==[dict(method='sendMessage',text=p['answer'])]
 c.create(ROOT+':original_uncertain',old)
 token=os.environ['CHINA_TELEGRAM_BOT_TOKEN']
 def tg(method,body):
  r=requests.post('https://api.telegram.org/bot'+token+'/'+method,json=body,timeout=(10,60));j=r.json()
  if not r.ok or not j.get('ok'):raise RuntimeError('Telegram read/delivery rejected HTTP '+str(r.status_code))
  return j['result']
 assert tg('getMe',{})['id']==8780468043
 c.put(ROOT+':recovery_claim',dict(status='submitting',at=stamp()))
 try:r=tg('sendMessage',dict(chat_id=-1004342917488,text=p['answer'],reply_markup=p['reply_markup']))
 except Exception as ex:
  c.put(ROOT+':recovery_claim',dict(status='uncertain',reason=type(ex).__name__,at=stamp()));raise
 assert r['chat']['id']==-1004342917488 and type(r['message_id'])is int
 receipt=dict(status='sent',receipt=r,message_id=r['message_id'],sent_at=stamp(),answer_sha256=p['answer_sha256'],job_id=343,recovery_scope=ROOT+':owner_recovery')
 c.put(ROOT+':recovery_receipt',receipt);c.put(ROOT+':part:0',receipt)
 c.put('china_agent:price_report_message:v1:'+str(r['message_id']),dict(status='sent',chat_id=-1004342917488,bot_id=8780468043,message_id=r['message_id'],report_job_id=343,report_date='2026-11-17',report_sha256=p['answer_sha256'],expires_at=p['expires_at'],receipt_key=ROOT+':part:0',selection_count=0,execution_authorized=False))
 root=c.url.rsplit('/',1)[0];rows=requests.get(root+'/business_agent_jobs',params=dict(id='eq.343',select='tool_trace,answer'),headers=c.h,timeout=30).json();assert len(rows)==1 and rows[0]['answer']==p['answer']
 trace=[x for x in rows[0]['tool_trace']if x.get('name')!='china_report_delivery']+[dict(name='china_report_delivery',sent_parts=1,message_ids=[r['message_id']],receipt_keys=[ROOT+':part:0'],report_sha256=p['answer_sha256'])]
 rr=requests.patch(root+'/business_agent_jobs',params=dict(id='eq.343'),headers=c.h,json=dict(status='done',error=None,completed_at=stamp(),lease_until=None,tool_trace=trace),timeout=30);rr.raise_for_status()
 c.put(ROOT,dict(status='sent',job_id=343,message_ids=[r['message_id']],receipt_keys=[ROOT+':part:0'],answer_sha256=p['answer_sha256'],completed_at=stamp(),wb_writes=0))
 c.put(ROOT+':recovery_claim',dict(status='verified',message_id=r['message_id'],at=stamp()))
 c.put('china_agent:price_clock:v1:health:intraday',dict(day='2026-11-17',mode='intraday',status='delivered',needs_attention=False,checked_at=stamp(),wb_writes=0,message_ids=[r['message_id']]))
 print(json.dumps(dict(status='sent',message_id=r['message_id'],wb_writes=0,model_calls=0)))
if __name__=='__main__':main()
