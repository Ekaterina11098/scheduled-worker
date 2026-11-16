"""Repair deterministic pre-HTTP notice rejection; no marketplace token or reads/writes."""
import json,os
from datetime import datetime,timezone
import requests
from china_cloud_cost_control import Cache,stamp
ROOT='china_agent:owner_funding_fix:2026-11-16:v1'
PID='daily-2026-11-16-budgets-1-buttons-989c2b630168b6cbb1d4dbd0-5122667182'
KEY='china_agent:daily_ad_result:v2:'+PID+':verified'
def main():
 c=Cache();e=c.get('china_agent:daily_ad_execution:v2:'+PID);p=c.get('china_agent:loss_plan:v1:'+PID)
 from china_execution_notice import proven
 byid={i['id']:i for i in p['items']}
 assert len(e['items'])==5 and all(proven(byid[s['id']],s)for s in e['items'])
 original=c.get(KEY);assert original['status']=='uncertain'and original['phase']=='verified'
 approval=c.get('china_agent:loss_plan_approval:v1:334');assert approval['result_message_id']==1056
 # owner_funding_fix16 guard explicitly rejects editMessageText before calling
 # its saved HTTP request method. The normal sender selected this edit branch.
 import inspect,owner_funding_fix16
 source=inspect.getsource(owner_funding_fix16)
 assert "in('getMe','getChatMember','sendMessage')"in source and "in('getMe','getChatMember','sendMessage','editMessageText')"not in source
 assert c.create(ROOT+':notice_previous_guard_rejection',dict(original,classification='not_attempted',proof='commit93f248d guard rejected editMessageText before original HTTP dispatch'))
 assert c.create(ROOT+':notice_recovery',dict(status='editing',message_id=1056,started_at=stamp(),WB_calls=0))
 body=dict(chat_id=-1004342917488,message_id=1056,text=original['text'],reply_markup=dict(inline_keyboard=[]))
 try:
  response=requests.post('https://api.telegram.org/bot'+os.environ['CHINA_TELEGRAM_BOT_TOKEN']+'/editMessageText',json=body,timeout=45);value=response.json()
 except Exception:
  c.put(ROOT+':notice_recovery',dict(status='uncertain',message_id=1056,WB_calls=0));raise RuntimeError('Notice edit uncertain; no replay')from None
 if not response.ok or value.get('ok')is not True:
  c.put(ROOT+':notice_recovery',dict(status='rejected',message_id=1056,http_status=response.status_code,description=value.get('description'),WB_calls=0));raise RuntimeError('Notice edit rejected')
 receipt=value['result'];assert receipt['message_id']==1056 and receipt['chat']['id']==-1004342917488 and receipt['from']['id']==8780468043
 record=dict(original,status='sent',receipt=receipt,message_id=1056,sent_at=stamp(),delivery_method='editMessageText',recovery_key=ROOT+':notice_recovery')
 c.put(KEY,record)
 c.put('china_agent:loss_plan_approval:v1:334',dict(approval,status='completed',result_status='done',result_message_id=1056))
 recovered=c.get(ROOT+':recovery');recovered.update(delivery_status='sent',delivery_message_id=1056,notice_recovered_at=stamp());c.put(ROOT+':recovery',recovered)
 c.put(ROOT+':notice_recovery',dict(status='sent',message_id=1056,receipt=receipt,completed_at=stamp(),WB_calls=0))
 print(json.dumps(dict(status='sent',message_id=1056,WB_calls=0)))
if __name__=='__main__':main()

