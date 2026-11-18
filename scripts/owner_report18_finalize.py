"""Read-only diagnosis and exact two-report revision; no WB writes or sends."""
import os,json,time,copy,base64,hashlib,math
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
from china_daily_ad_actions import plan,bind,BIND
from china_report_buttons import prepare as buttons,claim,ROOT as BUTTONS
from china_loss_control import PLAN,CHAT,BOT,digest
from china_advertising_v2_png import render
from china_morning_readiness import current_prices
from china_moysklad_read import read_stock
from china_owner_test18_contract import KEY,check_record
DAY='2026-11-18';ROOT='china_agent:owner_report18_fix:v2';KEEP={2128836688,2129199357,2129309884,2129309885}
def stamp():return datetime.now(timezone.utc).isoformat()
def store(io,k,v):io.put(k,v)if io.get(k)is not None else io.create(k,v)
def main():
 import requests
 io=AdvertisingIO();authority=io.get('china_agent:owner_report18_fix:v1:request');assert authority['owner_id']==5122667182 and authority['report_edit_authorized']is True and authority['wb_execution_authorized']is False
 assert not io.get(ROOT+':journal'),'Existing publication journal; inspect, no blind repeat'
 old=io.get('china_agent:advertising_artifacts:'+DAY+':v2');delivery=io.get('china_agent:advertising_delivery:'+DAY+':v1');assert delivery['status']=='delivered'
 def unclaimed():
  for f in old['files']:
   assert not io.get('china_agent:daily_ad_execution:v2:'+f['plan_id']),'An original report is already executing'
   assert not(io.get('china_agent:daily_action_claim:v1:'+f['plan_id'])or{}).get('domains'),'Original report already confirmed'
 unclaimed();assert io.create(ROOT+':claim',dict(status='collecting',created_at=stamp()))
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path
  if u.hostname==urlparse(io.url).hostname:ok=path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and path in('/api/advert/v2/adverts','/api/advert/v1/config'))or(m=='POST'and path=='/api/advert/v2/budget')
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and path=='/api/v2/list/goods/filter'
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and path.startswith('/api/remap/1.2/')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and path=='/api/v3/stocks/2373413'
  elif u.hostname=='api.telegram.org':ok=m=='POST'and path.rsplit('/',1)[-1]=='editMessageMedia'
  else:ok=False
  assert ok,'Read/report scope forbids mutation,send,or unrelated transport '+m+' '+str(u.hostname)+path
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:
  previous=io.get('china_agent:owner_report18_fix:v1:preview');fresh=io.get('china_agent:owner_report18_fix:v1:fresh')
  assert previous['status']=='prepared' and not io.get('china_agent:owner_report18_fix:v1:journal')
  assert (datetime.now(timezone.utc)-datetime.fromisoformat(fresh['observed_at'])).total_seconds()<7200
  bundle=copy.deepcopy(previous['bundle']);amount=previous['amount_cny'];reference=previous['reference_cny'];balance=previous['balance']
  action=bundle['owner_final_budget_review']['campaigns']['41779660']['action']
  source=copy.deepcopy(io.get('china_agent:advertising_source:'+DAY+':v2'))
  from china_advertising_v2 import compact_execution_records
  restored=[]
  for rec in source['executions']:
   key=rec.get('cache_key','')
   if key.startswith('china_agent:daily_ad_execution:v2:daily-2026-11-17-owner-approved-r2-budgets-1'):
    raw=io.get(key);assert raw is not None
    rec=compact_execution_records([dict(cache_key=key,payload=raw)])[0];restored.append(key)
   source['executions'][source['executions'].index(next(x for x in source['executions']if x.get('cache_key')==key))]=rec
  assert restored
  minima={str(c['id'])+':'+str(r['nm']):r['minimum_bid_minor']for c in bundle['campaigns']for r in c.get('focus',[])if type(r.get('minimum_bid_minor'))is int}
  from china_advertising_decision_contract import finalize,effective_launch_at
  states={c['id']:c for b in source['batches'].values()for c in b['campaigns']['adverts']}
  assert effective_launch_at(source,states[41332083]).startswith('2026-11-09')
  bundle=finalize(io,bundle,source,minima)
  # A funding-only resume is not a new test; actual additions, prices and bids still reset SKU windows.
  pages=render(bundle);assert [p['family']for p in pages]==['drr','budgets']
  oldplans=[io.get(PLAN+f['plan_id'])for f in old['files']];oldactions={a['id']:a for p in oldplans for a in p['items']};newactions={a['id']:a for f in pages for a in f['actions']}
  changed=[k for k in oldactions if k not in newactions or digest([oldactions[k]])!=digest([newactions[k]])]
  audit=dict(restored_receipts=restored,changed_previous_actions=changed,new_actions=[v for k,v in newactions.items()if k not in oldactions],campaigns=[dict(id=c['id'],status=c['status'],drr=c.get('drr'),notes=c.get('direction_recommendations'),focus=[dict(article=r['article'],decision=r.get('decision'),action=r.get('action'),blocker=r.get('data_blocker'),window=r.get('decision_window'))for r in c.get('focus',[])])for c in bundle['campaigns']])
  assert io.create(ROOT+':audit',audit)
  # Review an unexpected changed proposal before replacing an already delivered report.
  assert not changed, 'Previous actions changed; inspect audit before publication'
  assert newactions[action['id']]==action
  assert io.create(ROOT+':source',source)
  from china_report_preflight import freeze_contracts
  freeze_contracts(io,pages,bundle.get('proposal_preparation_contracts'))
  preview=dict(status='prepared',bundle=bundle,amount_cny=amount,reference_cny=reference,balance=balance,files=[dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],actions=f['actions'],b64=base64.b64encode(f['bytes']).decode(),sha256=hashlib.sha256(f['bytes']).hexdigest())for f in pages],wb_writes=0,telegram_calls=0)
  assert io.create(ROOT+':preview',preview)
  for _ in range(60):
   qa=io.get(ROOT+':visual_qa')or{}
   if qa.get('status')=='passed'and qa.get('image_hashes')==[f['sha256']for f in preview['files']]:break
   time.sleep(10)
  else:raise ValueError('Visual QA not received; no Telegram changes')
  unclaimed();state=dict(status='prepared',parts=[],wb_writes=0,model_calls=0,created_at=stamp());assert io.create(ROOT+':journal',state)
  assert io.create(ROOT+':before',dict(files=[{k:v for k,v in f.items()if k!='b64'}for f in old['files']],delivery=delivery))
  for p in oldplans:
   claim(io,p['plan_id'],[p['family']],'replace:'+ROOT);p.update(invalidated_at=stamp(),invalidation_reason='Owner-requested budget and completed risk explanation correction18Nov');io.put(PLAN+p['plan_id'],p)
  files=[]
  for index,f in enumerate(pages):
   p=plan(io,DAY,f,index,slot='owner-review18-r2');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256']);markup=buttons(io,p,f['family'])
   part=next(v for v in delivery['parts']if v['kind'].split(':')[0]==f['family']);mid=part['message_id'];assert mid in(1089,1090)
   cap='Китай · '+('реклама'if f['family']=='drr'else'бюджеты')+' · '+DAY+'. Рекомендации уточнены. Новых действий: '+str(len(p['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
   record=dict(family=f['family'],message_id=mid,status='editing',plan_id=p['plan_id'],plan_sha256=p['plan_sha256']);state['parts'].append(record);io.put(ROOT+':journal',state)
   try:
    rr=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=CHAT,message_id=mid,media=json.dumps(dict(type='photo',media='attach://photo',caption=cap),ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('report.png',f['bytes'],'image/png')},timeout=60)
    j=rr.json();assert rr.ok and j.get('ok');receipt=j['result'];assert receipt['message_id']==mid and receipt['chat']['id']==CHAT and receipt['reply_markup']==markup
   except Exception:
    record['status']='uncertain';state['status']='uncertain';io.put(ROOT+':journal',state);raise
   record.update(status='edited',receipt=receipt);io.put(ROOT+':journal',state)
   io.put(BIND+str(mid),dict(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],chat_id=CHAT,family=f['family']))
   token=markup['inline_keyboard'][0][0]['callback_data'].split(':')[1]
   store(io,BUTTONS+'message:'+str(mid),dict(status='sent',token=token,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],family=f['family'],chat_id=CHAT,bot_id=BOT,message_id=mid,receipt=receipt))
   bind(io,f,receipt)
   files.append(dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']),png_sha256=hashlib.sha256(f['bytes']).hexdigest(),b64=base64.b64encode(f['bytes']).decode()))
   part.update(receipt=receipt,corrected_by=ROOT,corrected_at=stamp(),sha256=hashlib.sha256(f['bytes']).hexdigest())
  io.put('china_agent:advertising_source:'+DAY+':v2',source)
  old.update(bundle=bundle,files=files,corrected_by=ROOT);io.put('china_agent:advertising_artifacts:'+DAY+':v2',old);io.put('china_agent:advertising_delivery:'+DAY+':v1',delivery)
  for f in files:assert io.get(PLAN+f['plan_id'])['report_message_ids']==[1089 if f['family']=='drr' else 1090]
  state.update(status='delivered',completed_at=stamp(),amount_cny=amount,reference_cny=reference,total_actions=sum(f['action_count']for f in files));io.put(ROOT+':journal',state)
  print(json.dumps(dict(status='delivered',message_ids=[1089,1090],funding_proposal_cny=amount,wb_writes=0,telegram_new_messages=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
