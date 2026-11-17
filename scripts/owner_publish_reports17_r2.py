"""Publish the exact owner-reviewed pair once. No marketplace or model requests."""
import base64,copy,hashlib,json,lzma
from datetime import datetime,timezone
from urllib.parse import urlparse
ROOT='china_agent:owner_publish_reports:2026-11-17:r2'
def main():
 import requests
 from china_advertising_state import AdvertisingIO
 from china_advertising_v2_png import render
 from china_daily_ad_actions import plan,bind
 from china_report_buttons import prepare
 from china_loss_control import PLAN,CHAT,digest
 io=AdvertisingIO()
 old=io.get(ROOT+':delivery')
 if old and old.get('status')=='delivered':print(json.dumps({'status':'already_delivered','message_ids':[p['message_id']for p in old['parts']]}));return
 assert not old,'Existing delivery journal: inspect receipts; never repeat blindly'
 raw=io.get(ROOT+':approved_package');assert raw and raw['encoding']=='lzma_base64'
 data=lzma.decompress(base64.b64decode(raw['data']));assert hashlib.sha256(data).hexdigest()==raw['sha256']
 package=json.loads(data);bundle=package['bundle'];manifest=package['manifest']
 assert manifest['status']=='approved_for_publication_only'and manifest['grants_action_permission']is False
 pages=render(bundle);assert [f['family']for f in pages]==['drr','budgets']
 assert [len(f['actions'])for f in pages]==[35,7]and [digest(f['actions'])for f in pages]==manifest['action_sha256']
 expected={'40933588':850,'41155909':100,'41296359':100,'41298169':200,'41332083':550,'41680449':100,'41779660':200}
 assert {str(a['campaign_id']):a['amount_cny']for a in pages[1]['actions']}==expected and sum(expected.values())==2100
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  ok=u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  if u.hostname=='api.telegram.org':ok=m=='POST'and u.path.rsplit('/',1)[-1]=='sendPhoto'and str(kw.get('data',{}).get('chat_id'))==str(CHAT)
  assert ok,'Publication prohibits WB/model/unrelated requests'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def upsert(k,v):
  v=json.loads(json.dumps(v));prior=io.get(k)
  if prior is None:assert io.create(k,v)
  else:io.put(k,v)
  assert io.get(k)==v
 for k,v in package['contracts'].items():
  assert v['grants_action_permission']is False
  prior=io.get(k)
  if prior is None:assert io.create(k,v)
  else:assert prior==v,'Frozen contract changed'
 state=dict(status='prepared',created_at=datetime.now(timezone.utc).isoformat(),parts=[],wb_writes=0,model_calls=0,manifest=manifest)
 assert io.create(ROOT+':delivery',state)
 def save():io.put(ROOT+':delivery',copy.deepcopy(state))
 files=[];parts=[]
 for index,f in enumerate(pages):
  p=plan(io,'2026-11-17',f,index,slot='owner-approved-r2');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'])
  keyboard=prepare(io,p,f['family']);assert keyboard
  caption='Китай · '+('реклама'if f['family']=='drr'else'бюджеты')+' · 17.11.2026. Новых действий: '+str(len(p['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
  if f['family']=='budgets':caption+=' Пополнения: 7, всего 2 100 CNY. Зависимые пополнения и запуск — после изменений из рекламного отчёта.'
  row=dict(status='sending',family=f['family'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']));state['parts'].append(row);save()
  try:
   response=requests.post('https://api.telegram.org/bot'+io.bot+'/sendPhoto',data=dict(chat_id=CHAT,caption=caption,reply_markup=json.dumps(keyboard,ensure_ascii=False)),files={'photo':('report.png',f['bytes'],'image/png')},timeout=60)
   value=response.json();assert response.ok and value.get('ok');receipt=value['result']
   assert receipt['chat']['id']==CHAT and receipt.get('message_id')and receipt['reply_markup']==keyboard
  except Exception:
   row['status']='uncertain';state['status']='uncertain';save();raise
  row.update(status='sent',message_id=receipt['message_id'],receipt=receipt);save()
  bind(io,f,receipt)
  files.append(dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']),b64=base64.b64encode(f['bytes']).decode()))
  parts.append(dict(status='sent',kind=f['kind'],message_id=receipt['message_id'],receipt=receipt,sha256=hashlib.sha256(f['bytes']).hexdigest()))
  assert io.get(PLAN+p['plan_id'])['report_message_ids']==[receipt['message_id']]
 artifacts='china_agent:advertising_artifacts:2026-11-17:v2';delivery='china_agent:advertising_delivery:2026-11-17:v1'
 previous=io.get(artifacts)or{};prior_delivery=io.get(delivery)or{}
 assert io.create(ROOT+':previous_delivery',prior_delivery)
 previous.update(bundle=bundle,files=files,corrected_by=ROOT,published_at=datetime.now(timezone.utc).isoformat());upsert(artifacts,previous)
 prior_delivery.update(status='delivered',parts=parts,corrected_by=ROOT,published_at=datetime.now(timezone.utc).isoformat());upsert(delivery,prior_delivery)
 state.update(status='delivered',completed_at=datetime.now(timezone.utc).isoformat(),total_funding_cny=2100);save()
 print(json.dumps(dict(status='delivered',message_ids=[p['message_id']for p in parts],action_counts=[35,7],total_funding_cny=2100,wb_writes=0,model_calls=0)))
if __name__=='__main__':main()
