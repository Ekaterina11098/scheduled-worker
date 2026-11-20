"""Publish two exact reviewed PNGs once. No WB calls or paid model."""
import json,hashlib,lzma,base64,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
ROOT='china_agent:owner_publish_reports:2026-11-20:r1'
def main():
 import requests
 from china_advertising_state import AdvertisingIO
 from china_daily_ad_actions import plan,bind
 from china_report_buttons import prepare
 from china_loss_control import CHAT,PLAN,digest
 io=AdvertisingIO();previous=io.get(ROOT+':delivery')
 if previous:
  assert previous['status']=='delivered','Inspect existing journal; never resend uncertain'
  print(json.dumps(dict(status='already_delivered',message_ids=[p['message_id']for p in previous['parts']])));return
 env=io.get(ROOT+':approved_package');assert env['status']=='approved_for_publication_only'
 data=lzma.decompress(base64.b64decode(''.join(io.get(k)['data']for k in env['parts'])));assert hashlib.sha256(data).hexdigest()==env['sha256']
 package=json.loads(data);assert package['grants_action_permission']is False and package['day']=='2026-11-20'
 assert len(package['pages'])==2
 assert [digest(p['actions'])for p in package['pages']]==package['action_sha256']
 assert sum(a['amount_cny']for a in package['pages'][1]['actions'])==package['total_cny']
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);ok=u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and method.upper()in('GET','POST','PATCH')
  if u.hostname=='api.telegram.org':ok=method.upper()=='POST'and u.path.rsplit('/',1)[-1]=='sendPhoto'and str(kw.get('data',{}).get('chat_id'))==str(CHAT)
  assert ok,'Publication forbids WB/model/unrelated requests'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 for k,v in package['contracts'].items():
  prior=io.get(k)
  if prior is None:assert io.create(k,v)
  else:assert prior==v,'Frozen contract changed'
 state=dict(status='prepared',created_at=datetime.now(timezone.utc).isoformat(),parts=[],wb_writes=0,model_calls=0,total_funding_cny=package['total_cny'])
 assert io.create(ROOT+':delivery',state)
 def save():io.put(ROOT+':delivery',copy.deepcopy(state))
 artifacts=[]
 for index,f in enumerate(package['pages']):
  data=base64.b64decode(f['b64']);assert hashlib.sha256(data).hexdigest()==f['png_sha256']
  p=plan(io,'2026-11-20',f,index,slot='owner-approved-r1');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'])
  keyboard=prepare(io,p,f['family']);assert keyboard
  caption=f['caption']
  row=dict(status='sending',family=f['family'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],png_sha256=f['png_sha256'],action_count=len(p['items']));state['parts'].append(row);save()
  try:
   r=requests.post('https://api.telegram.org/bot'+io.bot+'/sendPhoto',data=dict(chat_id=CHAT,caption=caption,reply_markup=json.dumps(keyboard,ensure_ascii=False)),files={'photo':('report.png',data,'image/png')},timeout=60)
   v=r.json();assert r.ok and v.get('ok');receipt=v['result'];assert receipt['chat']['id']==CHAT and receipt['message_id']and receipt['reply_markup']==keyboard
  except Exception:row['status']='uncertain';state['status']='uncertain';save();raise
  row.update(status='sent',message_id=receipt['message_id'],receipt=receipt);save()
  bind(io,f,receipt)
  assert io.get(PLAN+p['plan_id'])['report_message_ids']==[receipt['message_id']]
  assert io.get('china_agent:daily_ad_message:v2:'+str(receipt['message_id']))['plan_sha256']==p['plan_sha256']
  artifacts.append(copy.deepcopy(f))
 state.update(status='delivered',completed_at=datetime.now(timezone.utc).isoformat());save()
 assert io.create(ROOT+':artifacts',dict(status='delivered',files=artifacts,source_day='2026-11-20',bundle=package['bundle']))
 io.put('china_agent:advertising_delivery:2026-11-20:v1',dict(status='delivered',parts=state['parts'],corrected_by=ROOT,total_funding_cny=package['total_cny'],published_at=state['completed_at']))
 print(json.dumps(dict(status='delivered',parts=len(state['parts']),wb_writes=0,model_calls=0)))
if __name__=='__main__':main()

