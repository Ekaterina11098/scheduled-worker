"""Owner-requested full report correction. WB read-only; edits only the two bound photos."""
import base64,copy,json,hashlib
from datetime import datetime,timezone
from urllib.parse import urlparse
DAY='2026-11-17';ROOT='china_agent:owner_selected_test_report:'+DAY+':v1';IDS={41296359,41325637,41779660,41925305}

def main():
 import requests
 from china_advertising_state import AdvertisingIO
 from china_daily_ad_actions import plan,bind,BIND
 from china_report_buttons import prepare as buttons,claim,ROOT as BUTTONS
 from china_loss_control import PLAN,CHAT,BOT
 from china_advertising_v2_png import render
 io=AdvertisingIO();journal=io.get(ROOT+':report')
 if journal and journal.get('status')=='delivered':return
 assert not journal,'Existing edit journal; inspect receipts, never blindly repeat'
 key='china_agent:advertising_artifacts:'+DAY+':v2';dk='china_agent:advertising_delivery:'+DAY+':v1'
 old=io.get(key);delivery=io.get(dk);assert delivery['status']=='delivered'
 def unclaimed():
  for f in old['files']:
   assert not io.get('china_agent:daily_ad_execution:v2:'+f['plan_id']),'Report execution already started'
   assert not(io.get('china_agent:daily_action_claim:v1:'+f['plan_id'])or{}).get('domains'),'Report already confirmed'
 unclaimed()
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(io.url).hostname:ok=u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=False
  elif u.hostname=='api.telegram.org':ok=m=='POST'and u.path.rsplit('/',1)[-1]=='editMessageMedia'
  else:ok=False
  assert ok,'Correction forbids marketplace mutations and unrelated sends'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 from china_campaign_routes import guangzhou_models
 from selected_test17_plan import correction
 fresh=io.get('china_agent:owner_risk_review:'+DAY+':v1:fresh')
 source=io.get('china_agent:advertising_source:'+DAY+':v2');inputs=io.get('china_agent:advertising_full_growth:'+DAY+':v1:inputs')
 route=io.get('china_agent:campaign_economics_routes:v1')['campaigns']['41779660']
 models=guangzhou_models(inputs,route,dict(stock=fresh['stock_guangzhou'],cards=fresh['gua_cards'],published=fresh['published_guangzhou']),io.get('china_agent:new_ad_economics_policy:v1'))
 bundle,action=correction(old['bundle'],source,models,fresh)
 pages=render(bundle);assert [f['family']for f in pages]==['drr','budgets'],'Keep exactly two agreed PNGs'
 oldplans=[io.get(PLAN+f['plan_id'])for f in old['files']];assert all(oldplans)
 oldids={a['id']for p in oldplans for a in p['items']};newids={a['id']for f in pages for a in f['actions']}
 removed={a['id']for p in oldplans for a in p['items']if a.get('campaign_id')==41779660}
 assert len(removed)==4 and oldids-newids==removed and len(newids-oldids)==16,'Only withdraw obsolete paused-only cuts; preserve other actions'
 unclaimed()
 from china_loss_control import digest
 from china_selected_campaign_test import validate_contract
 contract=dict(status='ready_for_human_confirmation',grants_action_permission=False,action_sha256=digest([action]),maximum_funding_cny=200,expires_at=__import__('datetime').datetime.fromisoformat(action['recovery_evidence']['observed_at'].replace('Z','+00:00'))+__import__('datetime').timedelta(hours=24))
 contract['expires_at']=contract['expires_at'].isoformat()
 prior=io.get(action['selected_test_contract'])
 if prior:assert prior==contract,'Frozen test proposal changed'
 else:assert io.create(action['selected_test_contract'],contract)
 prep=copy.deepcopy(bundle['selected_test_preparation']);ref=prep.pop('key');prep['expires_at']=contract['expires_at']
 prior=io.get(ref)
 if prior:assert prior==prep,'Preparation changed'
 else:assert io.create(ref,prep)
 state=dict(status='prepared',created_at=datetime.now(timezone.utc).isoformat(),parts=[],wb_writes=0,model_calls=0)
 assert io.create(ROOT+':report',state);assert io.create(ROOT+':before',dict(bundle=old['bundle'],files=[{k:v for k,v in f.items()if k!='b64'}for f in old['files']]));assert io.create(ROOT+':before_delivery',delivery)
 assert io.create(ROOT+':review',bundle)
 def save():io.put(ROOT+':report',copy.deepcopy(state))
 for p in oldplans:
  claim(io,p['plan_id'],[p['family']],'replace:'+ROOT)
  p.update(invalidated_at=datetime.now(timezone.utc).isoformat(),invalidation_reason='Owner requested complete four-campaign risk review in the same two PNGs');io.put(PLAN+p['plan_id'],p)
 files=[]
 for index,f in enumerate(pages):
  p=plan(io,DAY,f,index,slot='selected-test17-v1');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'])
  markup=buttons(io,p,f['family']);assert markup
  part=next(x for x in delivery['parts']if x['kind'].split(':')[0]==f['family']);mid=part['message_id'];assert mid in(1077,1078)
  cap='Китай · '+('реклама'if f['family']=='drr'else'бюджеты')+' · '+DAY+'. Общий отчёт: рекомендации уточнены кратко. Новых действий: '+str(len(p['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
  if f['family']=='drr':cap+=' Тест 41779660: состав и ставки — здесь; пополнение и запуск — отдельно в бюджетном PNG.'
  record=dict(family=f['family'],message_id=mid,status='editing',plan_id=p['plan_id'],plan_sha256=p['plan_sha256']);state['parts'].append(record);save()
  try:
   rr=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=CHAT,message_id=mid,
    media=json.dumps(dict(type='photo',media='attach://photo',caption=cap),ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('report.png',f['bytes'],'image/png')},timeout=60)
   j=rr.json();assert rr.ok and j.get('ok');receipt=j['result'];assert receipt['message_id']==mid and receipt['chat']['id']==CHAT and receipt['reply_markup']==markup
  except Exception:
   record['status']='uncertain';state['status']='uncertain';save();raise
  record.update(status='edited',receipt=receipt);save()
  io.put(BIND+str(mid),dict(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],chat_id=CHAT,family=f['family']))
  token=markup['inline_keyboard'][0][0]['callback_data'].split(':')[1]
  io.put(BUTTONS+'message:'+str(mid),dict(status='sent',token=token,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],family=f['family'],chat_id=CHAT,bot_id=BOT,message_id=mid,receipt=receipt))
  bind(io,f,receipt)
  files.append(dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']),b64=base64.b64encode(f['bytes']).decode()))
  part.update(receipt=receipt,corrected_by=ROOT,corrected_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(f['bytes']).hexdigest())
 old.update(bundle=bundle,files=files,corrected_by=ROOT);io.put(key,old);io.put(dk,delivery)
 for f in files:assert io.get(PLAN+f['plan_id'])['report_message_ids']==[1077 if f['family']=='drr'else 1078]
 state.update(status='delivered',completed_at=datetime.now(timezone.utc).isoformat(),new_actions=16,total_actions=sum(f['action_count']for f in files));save()
 print(json.dumps(dict(status='delivered',message_ids=[p['message_id']for p in state['parts']],new_actions=16,wb_writes=0,model_calls=0)))
if __name__=='__main__':main()

