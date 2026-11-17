"""Delete only the two reports explicitly withdrawn by the owner; no WB/model."""
import os,json,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
ROOT='china_agent:owner_withdraw_reports:2026-11-17:v1'
def main():
 from china_advertising_state import AdvertisingIO
 io=AdvertisingIO();old=io.get(ROOT)
 if old and old['status']=='deleted':return
 assert not old,'Existing deletion journal: inspect results, do not retry uncertain deletion'
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(io.url).hostname:ok=u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  else:ok=u.hostname=='api.telegram.org'and m=='POST'and u.path.rsplit('/',1)[-1]=='deleteMessage'and kw.get('json',{}).get('chat_id')==-1004342917488 and kw['json'].get('message_id')in(1077,1078)
  assert ok,'Owner deletion scope rejects this request'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 state=dict(status='deleting',owner_id=5122667182,message_ids=[1077,1078],parts=[],wb_writes=0,model_calls=0,created_at=datetime.now(timezone.utc).isoformat())
 assert io.create(ROOT,state)
 def save():io.put(ROOT,copy.deepcopy(state))
 for mid in(1077,1078):
  row=dict(message_id=mid,status='deleting');state['parts'].append(row);save()
  try:
   rr=requests.post('https://api.telegram.org/bot'+io.bot+'/deleteMessage',json=dict(chat_id=-1004342917488,message_id=mid),timeout=45)
   result=rr.json();assert rr.ok and result.get('ok')is True and result.get('result')is True
   row.update(status='deleted',receipt=result);save()
  except Exception:
   row['status']='uncertain';state['status']='uncertain';save();raise
 state.update(status='deleted',completed_at=datetime.now(timezone.utc).isoformat());save()
 print(json.dumps(dict(status='deleted',message_ids=[1077,1078],wb_writes=0,model_calls=0)))
if __name__=='__main__':main()

