"""Owner-requested full report correction. WB read-only; edits only the two bound photos."""
import base64,copy,json,hashlib
from datetime import datetime,timezone
from urllib.parse import urlparse
DAY='2026-11-17';ROOT='china_agent:owner_risk_review:'+DAY+':v1';IDS={41296359,41325637,41779660,41925305}
EXPECTED={(41296359,1473245498),(41296359,1473243818),(41296359,1473242765),(41779660,2129199360),(41779660,2129309885),(41779660,2128836687),(41779660,2129309882)}
def correction(bundle,source,inputs,fresh,route,policy):
 from china_campaign_routes import guangzhou_models
 from china_advertising_economic_review import apply
 from china_advertising_directions import attach
 result=copy.deepcopy(bundle);part=copy.deepcopy(bundle);part['campaigns']=[c for c in part['campaigns']if c['id']in IDS]
 s=copy.deepcopy(source)
 evidence=dict(stock=fresh['stock_guangzhou'],cards=fresh['gua_cards'],published=fresh['published_guangzhou'])
 models=guangzhou_models(inputs,route,evidence,policy);s['economics']['rows'].update(models['rows'])
 minima={}
 for cid,q in fresh['minimums']['rows'].items():
  for n in q['bids']:
   vals=[v['value']for v in n['bids']if v['currency']=='CNY'];assert len(vals)==1
   minima[cid+':'+str(n['nm_id'])]=vals[0]
 for c in part['campaigns']:
  c['balance']=fresh['budgets']['rows'][str(c['id'])]['total']
  if c['status']==11:c['focus']=[]
 part=apply(part,s,minima)
 actions={(c['id'],r['nm']):r for c in part['campaigns']for r in c.get('focus',[])if r.get('action')}
 assert set(actions)==EXPECTED,('Changed reviewed scope',sorted(actions))
 for c in part['campaigns']:
  if c['id']in(41779660,41925305):
   c.update(budget_action=None,financial_action=None,budget_review_required=True,budget_audit_state='reviewed_no_fund',
     budget_short_note='Оставить на паузе. Не пополнять и не возобновлять.',budget_recommendation='Оставить на паузе. Не пополнять и не возобновлять.')
  if c['id']==41296359:
   c.pop('owner_budget_refused',None)
   c.update(budget_action=None,budget_review_required=True,budget_audit_state='reviewed_no_fund',
    budget_short_note='Не пополнять до оценки снижения ставок и исключения 509.',budget_recommendation='Не пополнять до оценки снижения ставок и исключения 509.')
  if c['id']==41325637:
   c.update(budget_action=None,budget_short_note='Без пополнения. Новый состав оценить 18.11 по полному 17.11.',budget_recommendation='Без пополнения. Новый состав оценить 18.11 по полному 17.11.')
  result['campaigns']=[c if old['id']==c['id']else old for old in result['campaigns']]
 # Preserve every other ready recommendation exactly, and replace only these four campaigns.
 directions=attach(part,s)['recommendation_directions']
 for key,section in result['recommendation_directions'].items():
  section['rows']=[r for r in section['rows']if r.get('campaign_id')not in IDS]+directions[key]['rows']
  section.update(count=len(section['rows']),ready_count=sum(r.get('ready')is True for r in section['rows']))
 result['owner_risk_review']=dict(campaigns=sorted(IDS),new_actions=7,wb_writes=0,model_calls=0,
   fresh_key=ROOT+':fresh',route_economics='GUA exact warehouse/packaged weight; own buyout first, approved40%only without own sample')
 return result,models,evidence
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
 fresh=io.get(ROOT+':fresh');assert fresh and fresh['status']=='complete'and not fresh['errors']
 assert(datetime.now(timezone.utc)-datetime.fromisoformat(fresh['completed_at'])).total_seconds()<7200,'Refresh stale evidence'
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
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path=='/api/advert/v2/adverts'
  elif u.hostname=='api.telegram.org':ok=m=='POST'and u.path.rsplit('/',1)[-1]=='editMessageMedia'
  else:ok=False
  assert ok,'Correction forbids marketplace mutations and unrelated sends'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 source=io.get('china_agent:advertising_source:'+DAY+':v2');inputs=io.get('china_agent:advertising_full_growth:'+DAY+':v1:inputs')
 route=io.get('china_agent:campaign_economics_routes:v1')['campaigns']['41779660'];policy=io.get('china_agent:new_ad_economics_policy:v1')
 from china_advertising_v2 import http
 live=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,sorted(IDS))))['adverts']
 observed={c['id']:c for c in fresh['campaigns']['adverts']}
 for c in live:
  prev=observed[c['id']]
  assert c['status']==prev['status']and c['settings']==prev['settings']and sorted(c['nm_settings'],key=lambda n:n['nm_id'])==sorted(prev['nm_settings'],key=lambda n:n['nm_id']),'Campaign changed after evidence'
 bundle,models,evidence=correction(old['bundle'],source,inputs,fresh,route,policy)
 pages=render(bundle);assert [f['family']for f in pages]==['drr','budgets'],'Keep exactly two agreed PNGs'
 oldplans=[io.get(PLAN+f['plan_id'])for f in old['files']];assert all(oldplans)
 oldids={a['id']for p in oldplans for a in p['items']};newids={a['id']for f in pages for a in f['actions']}
 assert oldids<=newids and len(newids-oldids)==7,'Do not drop or repeat unrelated work'
 unclaimed()
 state=dict(status='prepared',created_at=datetime.now(timezone.utc).isoformat(),parts=[],wb_writes=0,model_calls=0)
 assert io.create(ROOT+':report',state);assert io.create(ROOT+':before',dict(bundle=old['bundle'],files=[{k:v for k,v in f.items()if k!='b64'}for f in old['files']]));assert io.create(ROOT+':before_delivery',delivery)
 assert io.create(ROOT+':review',bundle);assert io.create(ROOT+':routed_models',models)
 io.create('china_agent:campaign_route_evidence:'+DAY+':v1:41779660',evidence)
 io.create('china_agent:campaign_route_cards:v1:41779660',fresh['gua_cards'])
 def save():io.put(ROOT+':report',copy.deepcopy(state))
 for p in oldplans:
  claim(io,p['plan_id'],[p['family']],'replace:'+ROOT)
  p.update(invalidated_at=datetime.now(timezone.utc).isoformat(),invalidation_reason='Owner requested complete four-campaign risk review in the same two PNGs');io.put(PLAN+p['plan_id'],p)
 files=[]
 for index,f in enumerate(pages):
  p=plan(io,DAY,f,index,slot='risk-four17-v1');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'])
  markup=buttons(io,p,f['family']);assert markup
  part=next(x for x in delivery['parts']if x['kind'].split(':')[0]==f['family']);mid=part['message_id'];assert mid in(1077,1078)
  cap='Китай · '+('реклама'if f['family']=='drr'else'бюджеты')+' · '+DAY+'. Общий отчёт: добавлен разбор четырёх РК. Новых действий: '+str(len(p['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
  if f['family']=='drr':cap+=' Снижения в41779660 не включают запуск или пополнение.'
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
 state.update(status='delivered',completed_at=datetime.now(timezone.utc).isoformat(),new_actions=7,total_actions=sum(f['action_count']for f in files));save()
 print(json.dumps(dict(status='delivered',message_ids=[p['message_id']for p in state['parts']],new_actions=7,wb_writes=0,model_calls=0)))
if __name__=='__main__':main()

