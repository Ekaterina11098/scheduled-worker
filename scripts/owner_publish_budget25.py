"""Replace the disputed budget PNG once; no marketplace or model requests."""
import copy,hashlib,io,json,base64,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from PIL import Image,ImageDraw,ImageFont
from china_owner_cash25_contract import ROOT,AMOUNTS

def font(n,b=False):
 for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold'if b else'')+'.ttf','C:/Windows/Fonts/'+('arialbd.ttf'if b else'arial.ttf')]:
  try:return ImageFont.truetype(p,n)
  except OSError:pass
 raise ValueError('Report font unavailable')
def money(v):return f'{float(v):,.2f}'.replace(',',' ').replace('.',',')
def render(preview,bundle,texts):
 W=2400;im=Image.new('RGB',(W,4000),'#edf3f7');d=ImageDraw.Draw(im);navy='#193e52'
 d.rectangle((0,0,W,190),fill=navy)
 d.text((44,24),'Китай · бюджеты · 25.11.2026 · исправленный',font=font(43,True),fill='white')
 d.text((44,90),'На 3 дня: больший темп из среднего за 22–24.11 и вчерашнего. Остатки: 25.11, 09:07 МСК.',font=font(27),fill='white')
 d.text((44,135),'Пополнения только после подтверждения кнопками. Шубы — без пополнения и запуска.',font=font(25),fill='white')
 def lines(s,w,n,b=False):
  result=[]
  for para in str(s).split('\n'):
   line=''
   for word in para.split():
    test=(line+' '+word).strip()
    if line and d.textlength(test,font=font(n,b))>w:result.append(line);line=word
    else:line=test
   result.append(line)
  return result
 states={c['id']:c for c in bundle['campaigns']};y=215
 chosen=[r for r in preview['campaigns']if r['id']in AMOUNTS or r['id']==42022679]
 for r in chosen:
  c=states[r['id']];cid=r['id'];advice=texts[cid]
  title=lines('РК '+str(cid)+' · '+r['name'],715,29,True)
  adv=[]
  for k,p in enumerate(advice.split('\n')):adv.extend((s,k==0)for s in lines(p,720,29 if k==0 else 25,k==0))
  h=max(290,95+len(adv)*35,150+len(title)*35)
  d.rounded_rectangle((24,y,W-24,y+h),18,fill='white')
  for j,s in enumerate(title):d.text((44,y+16+j*35),s,font=font(29,True),fill=navy)
  yy=y+28+len(title)*35
  for j,s in enumerate(['Остаток: '+money(r['balance'])+' CNY','Резерв на 3 дня: '+money(r['reserve3'])+' CNY','Нехватка: '+money(r['gap'])+' CNY']):
   d.text((44,yy+j*41),s,font=font(27,j==0),fill='#111111')
  d.text((820,y+16),'Расходы и ДРР',font=font(28,True),fill=navy)
  body=['Вчера, 24.11: '+money(r['yesterday'])+' CNY','Расход 22–24.11: '+money(r['spend3'])+' CNY','Расчётный темп в день: '+money(r['pace'])+' CNY']
  for j,s in enumerate(body):d.text((820,y+65+j*39),s,font=font(26),fill='#111111')
  for yy,label,values in [(y+196,'ДРР 22–24.11: ',c['budget_period']),(y+236,'ДРР 24.11: ',c['last'])]:
   rate=100*values['spend']/values['amount']if values['amount']else None
   d.text((820,yy),label+('нет заказов'if rate is None else money(rate)+'%'),font=font(26,True),fill='#bd303e'if rate is not None and rate>5 else'#168447')
  d.text((1620,y+16),'Рекомендация по пополнению',font=font(27,True),fill=navy)
  for j,(s,bold) in enumerate(adv):d.text((1620,y+65+j*35),s,font=font(29 if bold else 25,bold),fill='#bd303e'if cid==42022679 else'#111111')
  y+=h+12
 footer=['Всего предложено: 4 800 CNY · 7 пополнений. У остальных 11 работающих РК расчётного запаса достаточно.',
         'Это денежный резерв, не подтверждение прибыльности. Рискованные тесты могут дать убыток; контроль — ежедневно.',
         'Снижение расходов после чистки состава заранее не заложено. Суммы округлены вверх до 50 CNY, минимум — 100 CNY.']
 for p in footer:
  for s in lines(p,W-88,25):d.text((44,y+18),s,font=font(25),fill='#536b79');y+=34
 out=io.BytesIO();im.crop((0,0,W,y+45)).save(out,format='PNG');return out.getvalue()

def main():
 import requests
 from china_advertising_state import AdvertisingIO
 from china_daily_ad_actions import plan,bind,BIND
 from china_report_buttons import prepare
 from china_loss_control import CHAT,PLAN,digest
 db=AdvertisingIO();old_delivery=db.get(ROOT+':delivery')
 if old_delivery:
  if old_delivery.get('status')=='delivered':print('Already delivered; no repeated Telegram call');return
  raise ValueError('Prior publication unresolved; inspect without resending')
 request=db.get(ROOT+':owner_request')or{}
 assert request.get('status')=='approved_for_publication_only'and request.get('total_cny')==4800
 preview=db.get('china_agent:owner_budget_review:2026-11-25:v1:cash_preview');assert preview['cash_total_cny']==4800
 saved=db.get('china_agent:advertising_artifacts:2026-11-25:v2');bundle=saved['bundle']
 source=db.get('china_agent:advertising_source:2026-11-25:v2');assert source['period_to']=='2026-11-24'
 adplan=db.get(PLAN+'daily-2026-11-25-drr-0');assert adplan and not adplan.get('invalidated_at')
 oldplan=db.get(PLAN+'daily-2026-11-25-budgets-1');assert oldplan.get('invalidated_at')
 # This transport process cannot contact WB, models, or another Telegram method/chat.
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);allowed=u.hostname==urlparse(db.url).hostname and u.path.startswith('/rest/v1/')and method.upper()in('GET','POST','PATCH')
  if u.hostname=='api.telegram.org':allowed=method.upper()=='POST'and u.path.rsplit('/',1)[-1]=='editMessageMedia'and str(kw.get('data',{}).get('chat_id'))==str(CHAT)and str(kw.get('data',{}).get('message_id'))=='1154'
  if not allowed:raise ValueError('Publication forbids marketplace/model/unrelated requests')
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 campaigns={c['id']:c for c in bundle['campaigns']};rows={r['id']:r for r in preview['campaigns']}
 texts={40933588:'Пополнить на 3 150 CNY.\nДенежный резерв на три дня.',
  41155909:'Пополнить на 200 CNY.\nПосле снижения ставки 119 по рекламному отчёту.',
  41270309:'Пополнить на 350 CNY.\nПосле исключений по рекламному отчёту. Продолжение теста с риском минуса.',
  41298169:'Пополнить на 350 CNY.\nДенежный резерв на три дня.',
  41325622:'Тест: пополнить на 100 CNY.\nЭкономика части атрибуций не подтверждена; есть риск минуса.',
  41332083:'Пополнить на 250 CNY.\nПосле исключений по рекламному отчёту. Продолжение теста с риском минуса.',
  42088552:'Пополнить на 400 CNY.\nТолько бюджет. Состав, ставки и статус не менять. Экономика неполная; есть риск минуса.',
  42022679:'Не пополнять и не запускать.\nСохраняем паузу по решению владельца.'}
 actions=[];contracts={}
 for cid,amount in AMOUNTS.items():
  c=campaigns[cid];assert c['status']==9 and rows[cid]['recommended_topup']==amount
  e=copy.deepcopy(c['campaign_budget_economics']);assert e['expected_bids']
  # No fictional profit or risk-to-positive conversion is made.
  e['risk_disclosed_before_confirmation']=True;e['cash_reserve_only']=True
  required=[copy.deepcopy(x)for x in adplan['items']if x['campaign_id']==cid and (x['kind']=='ad_exclude_sku'or x['kind']=='ad_set_bid'and x['target_minor']<x['old_minor'])]if cid in(41155909,41270309,41332083)else[]
  if cid in(41155909,41270309,41332083):assert required,'Companion cleanup missing'
  key=ROOT+':contract:'+str(cid)
  item=dict(id='owner-cash25:'+str(cid),kind='topup_campaign',campaign_id=cid,amount_cny=amount,
   status_before=9,balance_before=float(rows[cid]['balance']),target_balance=float(rows[cid]['balance'])+amount,
   nm_ids=sorted(map(int,e['expected_bids'])),budget_evidence=e,owner_cash25_contract=key,
   selection_family='budgets',completed_days=['2026-11-22','2026-11-23','2026-11-24'])
  actions.append(item);contracts[key]=dict(status='ready_for_human_confirmation',grants_action_permission=False,
   campaign_id=cid,maximum_funding_cny=amount,action_sha256=digest([item]),period_to='2026-11-24',
   risk_disclosed_before_confirmation=True,required_actions=required,source_preview='china_agent:owner_budget_review:2026-11-25:v1:cash_preview')
 assert len(actions)==7 and sum(x['amount_cny']for x in actions)==4800
 image=render(preview,bundle,texts);sha=hashlib.sha256(image).hexdigest()
 page=dict(kind='budgets:001',family='budgets',page=1,total=1,actions=actions)
 p=plan(db,'2026-11-25',page,0,slot='owner-cash-r1');page.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'])
 for key,value in contracts.items():
  prior=db.get(key)
  if prior:assert prior==value
  else:assert db.create(key,value)
 keyboard=prepare(db,p,'budgets');assert keyboard
 assert len(db.get('china_agent:report_buttons:v1:plan:'+__import__('hashlib').sha256((p['plan_id']+':'+p['plan_sha256']+':budgets').encode()).hexdigest()[:24])['items'])==7
 prepared=dict(status='prepared',png_sha256=sha,b64=base64.b64encode(image).decode(),plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],total_cny=4800,action_count=7,wb_writes=0,model_calls=0)
 if not db.get(ROOT+':prepared'):assert db.create(ROOT+':prepared',prepared)
 else:assert db.get(ROOT+':prepared')==prepared
 state=dict(status='editing',message_id=1154,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],png_sha256=sha,wb_writes=0,model_calls=0)
 assert db.create(ROOT+':delivery',state)
 caption='Китай · бюджеты · 25.11.2026 · исправленный. 7 пополнений: 4 800 CNY. Для трёх РК сначала выполните изменения рекламного отчёта. Шубы не пополняем. Пополнение — только после подтверждения кнопками.'
 media=dict(type='photo',media='attach://report',caption=caption)
 try:
  response=requests.post('https://api.telegram.org/bot'+db.bot+'/editMessageMedia',
   data=dict(chat_id=CHAT,message_id=1154,media=json.dumps(media,ensure_ascii=False),reply_markup=json.dumps(keyboard,ensure_ascii=False)),
   files={'report':('budget.png',image,'image/png')},timeout=60)
  result=response.json();assert response.ok and result.get('ok')
  receipt=result['result'];assert receipt['chat']['id']==CHAT and receipt['message_id']==1154 and receipt['reply_markup']==keyboard
 except Exception:
  state['status']='uncertain';db.put(ROOT+':delivery',state);raise
 state.update(status='edited',receipt=receipt,edited_at=datetime.now(timezone.utc).isoformat());db.put(ROOT+':delivery',state)
 oldbind=db.get(BIND+'1154')
 if not db.get(ROOT+':old_binding'):assert db.create(ROOT+':old_binding',oldbind)
 db.put(BIND+'1154',dict(plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],chat_id=CHAT,family='budgets'))
 bind(db,page,receipt)
 assert db.get(BIND+'1154')['plan_sha256']==p['plan_sha256']and db.get(PLAN+p['plan_id'])['report_message_ids']==[1154]
 delivery=db.get('china_agent:advertising_delivery:2026-11-25:v1')
 if not db.get(ROOT+':old_delivery'):assert db.create(ROOT+':old_delivery',delivery)
 for part in delivery['parts']:
  if part['kind']=='budgets:001':part.update(status='sent',receipt=receipt,message_id=1154,sha256=sha,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],delivery_method='editMessageMedia',revision_source_key=ROOT+':delivery')
 db.put('china_agent:advertising_delivery:2026-11-25:v1',delivery)
 state.update(status='delivered',delivery_method='editMessageMedia',normalized_status='sent',total_cny=4800,action_count=7,completed_at=datetime.now(timezone.utc).isoformat());db.put(ROOT+':delivery',state)
 print(json.dumps(dict(status='delivered',message_id=1154,total_cny=4800,action_count=7,wb_writes=0,model_calls=0)))
if __name__=='__main__':main()

