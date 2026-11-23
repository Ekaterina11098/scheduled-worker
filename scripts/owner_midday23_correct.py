import json,copy,hashlib,requests,base64,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_advertising_midday import render_midday
from china_daily_ad_actions import plan,bind,BIND
from china_report_buttons import prepare as keyboard,ROOT as BUTTON_ROOT
from china_daily_report_validity import publish
from china_loss_control import CHAT,BOT,PLAN
ROOT='china_agent:owner_midday23_correction:v1'
DROP={'40933588:1473244345','41325622:1535337770'}
def main():
 io=AdvertisingIO();old=io.get(ROOT)
 if old:
  if old.get('status')=='edited':print('Already edited');return
  raise RuntimeError('Existing correction claim; inspect no blind retry')
 assert io.create(ROOT,dict(status='preparing',wb_writes=0))
 orig=requests.sessions.Session.request
 def guard(s,m,url,*args,**kw):
  u=urlparse(url);ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m.upper()in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.telegram.org'and m.upper()=='POST'and u.path.rsplit('/',1)[-1]in('getMe','editMessageMedia'))
  assert ok,'Report edit only; no WB access';return orig(s,m,url,*args,**kw)
 requests.sessions.Session.request=guard
 assert io.tg('getMe',{})['id']==BOT
 saved=io.get('china_agent:advertising_midday_artifacts:2026-11-23:ready-v2');b=copy.deepcopy(saved['bundle']);removed=[]
 for c in b['campaigns']:
  keep=[]
  for r in c.get('attention',[]):
   if r['action']['id']in DROP:removed.append(r['action']['id'])
   else:keep.append(r)
  c['attention']=keep
  if c['id']in(40933588,41325622)and not keep:c['owner_review_note']='Сегодня ставка уже изменена; повторного повышения нет.'
 assert set(removed)==DROP
 for section in b.get('recommendation_directions',{}).values():
  section['rows']=[r for r in section.get('rows',[])if(r.get('action')or{}).get('id')not in DROP]
  section['count']=len(section['rows']);section['ready_count']=sum(r.get('ready')is True for r in section['rows']);section['unready_count']=section['count']-section['ready_count']
 files=render_midday(b);assert len(files)==2 and sum(len(f['actions'])for f in files)==6
 v=dict(status='prepared',removed=removed,parts=[],bundle=b,wb_writes=0)
 for i,(f,mid)in enumerate(zip(files,[1138,1139])):
  p=plan(io,'2026-11-23',f,i,slot='midday-corrected23')
  f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256']);markup=keyboard(io,p,'drr')or{'inline_keyboard':[[{'text':'‹ Главное меню','callback_data':'cmn1:home'}]]}
  caption='Китай · промежуточный отчёт · 2026-11-23 · '+str(i+1)+'/2. '+('Исправлено: 6 новых действий; повторные повышения убраны. Подтвердите по кнопкам.'if i==0 else'Новых действий для исполнения нет.')
  before=dict(daily=io.get(BIND+str(mid)),buttons=io.get(BUTTON_ROOT+'message:'+str(mid)))
  entry=dict(message_id=mid,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],status='editing',before_bindings=before,image_sha256=hashlib.sha256(f['bytes']).hexdigest());v['parts'].append(entry);io.put(ROOT,v)
  media=dict(type='photo',media='attach://photo',caption=caption)
  response=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=str(CHAT),message_id=str(mid),media=json.dumps(media,ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('midday.png',f['bytes'],'image/png')},timeout=(10,60));j=response.json();assert response.ok and j.get('ok')is True,'Telegram edit rejected'
  receipt=j['result'];assert receipt['chat']['id']==CHAT and receipt['message_id']==mid
  entry.update(status='edited',receipt=receipt,edited_at=datetime.now(timezone.utc).isoformat());io.put(ROOT,v)
  p['report_message_ids']=[mid];io.put(PLAN+p['plan_id'],p)
  io.put(BIND+str(mid),dict(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],chat_id=CHAT,family='drr'))
  if p['items']:
   token=markup['inline_keyboard'][0][0]['callback_data'].split(':')[1]
   io.put(BUTTON_ROOT+'message:'+str(mid),dict(status='sent',token=token,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],family='drr',chat_id=CHAT,bot_id=BOT,message_id=mid,receipt=receipt))
  bind(io,f,receipt);entry['bindings_verified']=True;io.put(ROOT,v)
 v.update(status='edited',completed_at=datetime.now(timezone.utc).isoformat());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],messages=[1138,1139],actions=6,wb_writes=0)))
if __name__=='__main__':main()

