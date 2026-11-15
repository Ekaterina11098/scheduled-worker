"""Correct the same two morning report photos; no marketplace writes/model calls."""
import json,copy,base64,hashlib,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:morning_report_repair:2026-11-15:v1';DAY='2026-11-15';CHAT=-1004342917488
def main():
 io=AdvertisingIO()
 if(io.get(ROOT)or{}).get('status')=='delivered':return
 assert not io.get(ROOT),'Existing correction journal must be reviewed, never replayed'
 old=io.get('china_agent:advertising_artifacts:'+DAY+':v2');delivery=io.get('china_agent:advertising_delivery:'+DAY+':v1')
 assert delivery['status']=='delivered'and len(old['files'])==2
 def unclaimed():
  for f in old['files']:
   assert not(io.get('china_agent:daily_action_claim:v1:'+f['plan_id'])or{}).get('domains'),'Owner already confirmed report; do not replace'
 unclaimed()
 original=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  u=urlparse(url);m=method.upper()
  if 'openai'in(u.hostname or''):raise ValueError('No model calls')
  if u.hostname=='advert-api.wildberries.ru':assert(m=='GET'and u.path in ['/adv/v1/promotion/count','/api/advert/v2/adverts','/adv/v3/fullstats','/api/advert/v1/config'])or(m=='POST'and u.path in ['/api/advert/v2/budget','/api/advert/v1/bids/min'])
  elif(u.hostname or'').endswith('wildberries.ru'):assert m=='GET'or m=='POST'and u.path.startswith('/api/v3/stocks/')
  elif u.hostname=='api.telegram.org':assert u.path.rsplit('/',1)[-1]=='editMessageMedia'
  elif(u.hostname or'').endswith('moysklad.ru'):assert m=='GET'
  elif not url.startswith(io.url+'/rest/v1/'):raise ValueError('No unrelated service calls')
  return original(session,method,url,**kw)
 requests.sessions.Session.request=guard
 # Reuse the completed saved source, preserving all existing growth proposals.
 from china_advertising_v2 import build
 from china_advertising_cards import enhance
 from china_advertising_economic_review import apply as economic
 from china_advertising_full_growth import enrich
 from china_advertising_directions import attach
 from china_budget_page_actions import owner_policy
 from china_morning_rules_review import review as rules
 from china_sales_growth_review import attach as sales
 from china_new_campaign_reporting import attach as new_campaigns
 from china_campaign_financial_review import apply as financial
 s=io.get('china_agent:advertising_source:'+DAY+':v2')
 assert s['day_quality']['usable']and s['period_to']=='2026-11-14'and s.get('full_growth_inputs')
 minima={}
 b=economic(enhance(build(s),s),s,minima)
 io.create(ROOT+':review',dict(economic_review_complete=b.get('economic_review_complete'),blockers=b.get('economic_review_blockers'),new_cost_actions=[r['action']for c in b['campaigns']for r in c.get('focus',[])if r.get('completed_cost_scan')and r.get('action')]))
 b=rules(io,owner_policy(io,attach(enrich(io,s,b),s)),s)
 b=sales(b);b['mandatory_campaign_format']=(io.get('china_agent:advertising_format:v2')or{}).get('mandatory')is True
 b=financial(io,new_campaigns(io,b),s,minima)
 from china_advertising_v2_png import render
 pages=render(b);assert len(pages)==2 and {f['family']for f in pages}=={'drr','budgets'}
 unclaimed()
 from china_daily_ad_actions import plan,BIND
 from china_report_buttons import prepare as buttons
 from china_loss_control import PLAN
 journal=dict(status='prepared',parts=[],created_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,model_calls=0)
 assert io.create(ROOT,journal)
 assert io.create(ROOT+':before',old)
 assert io.create(ROOT+':before_delivery',delivery)
 for f in old['files']:
  key=PLAN+f['plan_id'];p=io.get(key);p.update(invalidated_at=datetime.now(timezone.utc).isoformat(),invalidation_reason='Owner requested complete cost review in the same morning report');io.put(key,p)
 files=[]
 for index,f in enumerate(pages):
  p=plan(io,DAY,f,index,slot='cost-complete15')
  mid=next(r['message_id']for r in delivery['parts']if r['kind'].split(':')[0]==f['family'])
  markup=buttons(io,p,f['family']);caption='Китай · '+('реклама и рекомендации по РК'if f['family']=='drr'else'бюджеты')+' · '+DAY+'. Обновлённый общий отчёт. Новых действий: '+str(len(p['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
  part=dict(family=f['family'],message_id=mid,status='editing',plan_id=p['plan_id']);journal['parts'].append(part);io.put(ROOT,journal)
  try:
   media=dict(type='photo',media='attach://photo',caption=caption)
   r=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=CHAT,message_id=mid,media=json.dumps(media,ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('report.png',f['bytes'],'image/png')},timeout=60)
   j=r.json();assert r.ok and j.get('ok')and j['result']['message_id']==mid and j['result']['chat']['id']==CHAT
   part.update(status='edited',receipt=j['result']);io.put(ROOT,journal)
  except Exception:part['status']='uncertain';journal['status']='uncertain';io.put(ROOT,journal);raise
  io.put(BIND+str(mid),dict(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],chat_id=CHAT,family=f['family']))
  p['report_message_ids']=[mid];io.put(PLAN+p['plan_id'],p)
  from china_daily_report_validity import publish
  publish(io,p)
  token=markup['inline_keyboard'][0][0]['callback_data'].split(':')[1]if markup else None
  if token:io.put('china_agent:report_buttons:v1:message:'+str(mid),dict(status='sent',token=token,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],family=f['family'],chat_id=CHAT,bot_id=8780468043,message_id=mid,receipt=j['result']))
  dp=next(x for x in delivery['parts']if x['message_id']==mid)
  dp.update(sha256=hashlib.sha256(f['bytes']).hexdigest(),receipt=j['result'],corrected_by=ROOT)
  io.put('china_agent:advertising_delivery:'+DAY+':v1',delivery)
  files.append(dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']),b64=base64.b64encode(f['bytes']).decode()))
 old.update(bundle=b,files=files,corrected_by=ROOT);io.put('china_agent:advertising_artifacts:'+DAY+':v2',old)
 journal.update(status='delivered',completed_at=datetime.now(timezone.utc).isoformat());io.put(ROOT,journal)
 print(json.dumps(dict(status='delivered',message_ids=[p['message_id']for p in journal['parts']],wb_writes=0,model_calls=0)))
if __name__=='__main__':main()
