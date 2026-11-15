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
 from china_advertising_v2 import prepare
 b=prepare(io,DAY)
 from china_advertising_v2_png import render
 pages=render(b);assert len(pages)==2 and {f['family']for f in pages}=={'drr','budgets'}
 unclaimed()
 from china_daily_ad_actions import plan,BIND
 from china_report_buttons import prepare as buttons
 from china_loss_control import PLAN
 journal=dict(status='prepared',parts=[],created_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,model_calls=0)
 assert io.create(ROOT,journal)
 assert io.create(ROOT+':before',old)
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
  files.append(dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']),b64=base64.b64encode(f['bytes']).decode()))
 old.update(bundle=b,files=files,corrected_by=ROOT);io.put('china_agent:advertising_artifacts:'+DAY+':v2',old)
 journal.update(status='delivered',completed_at=datetime.now(timezone.utc).isoformat());io.put(ROOT,journal)
 print(json.dumps(dict(status='delivered',message_ids=[p['message_id']for p in journal['parts']],wb_writes=0,model_calls=0)))
if __name__=='__main__':main()
