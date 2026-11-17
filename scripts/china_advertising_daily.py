"""China-only daily read/PNG/send with frozen daily artifacts and durable receipts."""
import os,json,base64,hashlib,tempfile
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO as IO
from china_advertising_delivery import deliver,telegram_sender
def run():
 if os.environ.get('GITHUB_REPOSITORY')!='Ekaterina11098/veschi-bot-runner' or os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('Public main only')
 local=datetime.now(ZoneInfo('Europe/Moscow'));day=local.date().isoformat();io=IO()
 if (io.get('china_agent:advertising_delivery:'+day+':v1') or {}).get('status')=='delivered':
  print(json.dumps(dict(status='already_delivered',day=day,telegram_calls=0,wb_writes=0)));return
 review=io.get('china_agent:owner_full_growth_review:'+day+':v1') or {}
 if review.get('hold_delivery_until_reviewed') is True and review.get('status') not in ['reviewed','included']:
  print(json.dumps(dict(status='waiting_owner_requested_full_growth_review',day=day,telegram_calls=0,wb_writes=0)));return
 prepare_only=os.environ.get('CHINA_AD_PREPARE_ONLY')=='true'or local.hour*60+local.minute<450 and os.environ.get('CHINA_AD_FROZEN_ONLY')!='true'
 manual=io.get('china_agent:advertising_manual_delivery:'+day+':v1') or {}
 manual_ok=manual.get('owner_user_id')==5122667182 and manual.get('source_channel')=='codex' and manual.get('report_day')==day and manual.get('authorized') is True and datetime.now().timestamp()<datetime.fromisoformat(manual.get('expires_at','1970-01-01T00:00:00+00:00')).timestamp()
 if local.hour>=10 and not manual_ok:
  missed='china_agent:advertising_missed_slot:'+day+':v1';value=dict(status='late_send_blocked',observed_at=local.isoformat(),reason='Morning report must not arrive as stale afternoon report')
  io.put(missed,value)if io.get(missed)else io.create(missed,value)
  print('Morning delivery window closed; no stale Telegram send');return
 if (io.get('china_agent:advertising_delivery:'+day+':v1') or {}).get('status')=='delivered':
  print(json.dumps(dict(status='already_delivered',day=day,telegram_calls=0,wb_writes=0)));return
 key='china_agent:advertising_artifacts:'+day+':v2';saved=io.get(key)
 if not saved and os.environ.get('CHINA_AD_FROZEN_ONLY')=='true':raise ValueError('Morning preparation missing; delivery stage cannot collect WB data')
 if not saved:
  from china_advertising_v2 import prepare,VERSION
  from china_advertising_v2_png import render as render_grouped
  from china_daily_ad_actions import plan
  bundle=prepare(io,day)
  from china_report_preflight import stage_restarts
  bundle=stage_restarts(io,bundle)
  if bundle.get('reserve_preflight',{}).get('blocked_action_ids'):raise ValueError('Current addition reserve read unavailable; preparation must retry')
  pages=render_grouped(bundle);images=[]
  from china_report_preflight import freeze_contracts
  bundle['publication_preflight']=freeze_contracts(io,pages,bundle.get('proposal_preparation_contracts'))
  for index,f in enumerate(pages):
   p=plan(io,day,f,index)
   images.append(dict(kind=f['kind'],family=f['family'],page=f['page'],total=f['total'],plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],action_count=len(p['items']),png_sha256=hashlib.sha256(f['bytes']).hexdigest(),b64=base64.b64encode(f['bytes']).decode()))
  saved=dict(day=day,status='frozen',presentation=bundle.get('presentation'),bundle=bundle,files=images,wb_writes=0)
  if not io.create(key,saved):saved=io.get(key)
 if saved.get('day')!=day or saved.get('status')!='frozen':raise ValueError('Frozen image scope invalid')
 if prepare_only:
  print(json.dumps(dict(status='prepared',day=day,telegram_calls=0,wb_writes=0)));return
 from china_advertising_reserve import refresh_before_send
 saved=refresh_before_send(io,day,saved,key)
 from china_daily_ad_actions import bind
 from china_report_preflight import freeze_contracts
 rendered=[]
 for file in saved['files']:
  p=io.get('china_agent:loss_plan:v1:'+file['plan_id'])
  if not p or p['plan_sha256']!=file['plan_sha256']or __import__('china_loss_control').digest(p['items'])!=p['plan_sha256']:raise ValueError('Frozen PNG and actual button plan differ')
  if file.get('png_sha256')and hashlib.sha256(base64.b64decode(file['b64'])).hexdigest()!=file['png_sha256']:raise ValueError('Frozen report image changed')
  rendered.append(dict(family=file['family'],actions=p['items']))
 freeze_contracts(io,rendered,saved['bundle'].get('proposal_preparation_contracts'))
 files=[]
 for f in saved['files']:
  caption='Китай · '+('реклама' if f['family']=='drr' else 'бюджеты')+' · '+day+' · '+str(f['page'])+'/'+str(f['total'])+'. Новых действий: '+str(f['action_count'])+'.'
  caption+=(' Ответьте «Сделай всё» для новых действий только этого PNG.' if f['action_count'] else ' Готовых пополнений к исполнению нет; потребность и ограничения показаны в PNG.' if f['family']=='budgets' else ' Новых действий для исполнения нет.')
  files.append(dict(f,bytes=base64.b64decode(f['b64'],validate=True),caption=caption))
 sender=telegram_sender(io)
 target=local.replace(hour=7,minute=30,second=0,microsecond=0)
 if not manual_ok:
  import time
  while (remaining:=(target-datetime.now(ZoneInfo('Europe/Moscow'))).total_seconds())>0:time.sleep(min(remaining,1))
 result=deliver(io,day,files,sender,binder=lambda f,r:bind(io,f,r))
 print(json.dumps(dict(status=result['status'],day=day,message_ids=[x['message_id'] for x in result['parts']],wb_writes=0)))
if __name__=='__main__':run()