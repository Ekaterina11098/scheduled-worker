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
DAY='2026-11-18';ROOT='china_agent:owner_report18_fix:v1';KEEP={2128836688,2129199357,2129309884,2129309885}
def stamp():return datetime.now(timezone.utc).isoformat()
def store(io,k,v):io.put(k,v)if io.get(k)is not None else io.create(k,v)
def main():
 import requests
 io=AdvertisingIO();authority=io.get(ROOT+':request');assert authority['owner_id']==5122667182 and authority['report_edit_authorized']is True and authority['wb_execution_authorized']is False
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
  fresh=dict(observed_at=stamp(),campaigns=http(io,'/api/advert/v2/adverts?ids=41779660,41967612,41296359')['adverts'],budgets=http(io,'/api/advert/v2/budget','POST',dict(advertIds=[41779660,41967612,41296359]))['adverts'],config=http(io,'/api/advert/v1/config'))
  states={c['id']:c for c in fresh['campaigns']};budget={c['advertId']:c for c in fresh['budgets']}
  assert states[41779660]['status']==9 and {n['nm_id']for n in states[41779660]['nm_settings']}==KEEP
  assert states[41967612]['status']==9 and all(n['bids_kopecks']['search']==28 for n in states[41967612]['nm_settings'])
  assert fresh['config']['currency']=='CNY'
  prices=current_prices(io,sorted(KEEP));stock=read_stock([p['article']for p in prices['rows']],warehouse_role='guangzhou')
  assert stock['coverage_complete']and stock['warehouse_id']=='2233c6a7-d906-11f1-0a80-197e004df0d2'
  route=io.get('china_agent:campaign_economics_routes:v1')['campaigns']['41779660'];cards=io.get('china_agent:campaign_route_cards:v1:41779660')
  mapping={str(z['chrtID']):c['nmID']for c in cards['rows']if c['nmID']in KEEP for z in c['sizes']}
  rr=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/2373413',json=dict(chrtIds=list(map(int,mapping))),headers={'Authorization':io.token},timeout=50);rr.raise_for_status();pub=rr.json()
  amounts={n:0 for n in KEEP};seen=set()
  for z in pub['stocks']:
   n=mapping[str(z.get('chrtId',z.get('chrtID')))];seen.add(n);amounts[n]+=z['amount']
  assert seen==KEEP
  inputs=io.get(ROOT+':inputs');stockrows={r['article'].casefold():r for r in stock['rows']};members={};available=[]
  for row in prices['rows']:
   n=str(row['nm_id']);oldm=inputs['gua_models'][n];st=stockrows[row['article'].casefold()];assert row['seller_price']==oldm['seller_price_cny']and st['price']>0
   fx=oldm['fx_rub_per_cny'];q=oldm['buyout'];margin=q*(row['seller_price']*.72-st['price']/100/fx)-oldm['logistics_cny']
   free=st['stock']-st['reserve'];members[n]=dict(article=row['article'],price=row['seller_price'],cost=st['price']/100,fx=fx,buyout=q,logistics_cny=oldm['logistics_cny'],stock_free=free,published_stock=amounts[int(n)],expected_margin_before_ads_cny=margin)
   if free>0 and amounts[int(n)]>0:assert margin>0;available.append(int(n))
  assert available
  fresh.update(prices=prices,stock=stock,published=pub,member_inputs=members);assert io.create(ROOT+':fresh',fresh)
  balance=budget[41779660]['total'];reference=256.5;minimum=fresh['config']['minTopUp']/100
  amount=int(math.ceil(max(minimum,reference-balance)/50)*50);assert 100<=amount<=300 and balance<reference
  action=dict(id='owner-test18-topup:41779660',kind='topup_campaign',campaign_id=41779660,amount_cny=amount,balance_before=balance,target_balance=balance+amount,status_before=9,nm_ids=sorted(KEEP),manual_budget_continuation=True,owner_requested_test_20261118=True,manual_budget_contract=KEY,
   budget_evidence=dict(observed_at=stamp(),period_from='2026-11-16',period_to='2026-11-17',expected_bids={str(n['nm_id']):n['bids_kopecks']for n in states[41779660]['nm_settings']},warehouse_id=route['warehouse_id'],published_warehouse_id=route['published_warehouse_id'],size_to_nm=mapping,member_inputs=members,risk_disclosed_before_confirmation=True,first_full_post_change_day='2026-11-18',whole_campaign_profit_proven=False,reference_cny=reference,reference_basis='3 x max observed selected-four calendar-day spend16–17Nov:85.50,59.88; includes old higher bid conservatively, not3fullnewtestdays',owner_source_key=ROOT+':request'))
  contract=dict(status='ready_for_human_confirmation',grants_action_permission=False,owner_id=5122667182,source_owner_request=authority['quote'],risk_disclosed_before_confirmation=True,action_sha256=digest([action]),maximum_funding_cny=amount,expires_at='2026-11-18T20:59:00+00:00')
  assert io.create(KEY,contract);check_record(io,action,states[41779660])
  bundle=copy.deepcopy(old['bundle']);bundle['campaigns']=[c for c in bundle['campaigns']if c['id']!=40892162]
  byid={c['id']:c for c in bundle['campaigns']};c=byid[41779660];c['balance']=balance
  text='Тест: пополнить на '+str(amount)+' CNY. Состав 027/68/160/161 и ставки 0,28 сохранить. Плановый выкуп 40%; окупаемость ещё не доказана.'
  duration='Остаток проверен '+datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M')+' МСК. После пополнения около '+str(round((balance+amount)/85.5,1)).replace('.',',')+' дня при 85,50 CNY/день; темп может измениться.'
  c.update(owner_statistics_note='Оставить 027, 68, 160, 161 по 0,28 CNY. Первый полный день 18.11; оценка 19.11. Пополнение — в бюджетном PNG.',budget_duration_note=duration)
  review=bundle.setdefault('owner_final_budget_review',dict(owner_id=5122667182,campaigns={}))
  review['campaigns']['41779660']=dict(decision='owner_requested_test_20261118',proposal_only=True,risk_disclosed=True,action=action,reference_cny=reference,reference_label='Ориентир 3 дней состава 4 SKU: ',text=text)
  c=byid[41967612];c['balance']=budget[41967612]['total']
  c['owner_statistics_note']='Ставки 0,28 CNY — минимум; не повышать. 0/55/577/588: 234,64 CNY без прямых заказов. 209/587 дали 3 прямых заказа. Первый полный день 18.11; решение 19.11.'
  review['campaigns']['41967612']=dict(decision='no_fund',reference_cny=1023.96,reference_label='Ориентир по дню запуска, не прогноз: ',text='Дополнительное пополнение пока не предлагается. Из 10 атрибуций 3 по товарам РК, 7 сопутствующих. При условном учёте всех — около +5,40 CNY до неизвестных расходов; запас экономики недостаточен. Оценка 19.11.')
  byid[41296359]['owner_statistics_note']='210/529: снижены 17.11 с 0,34 до минимума 0,28 CNY. Сохранить до первой полной оценки 19.11. 509 уже исключён; старый расход включён в ДРР.'
  # Preserve every other approved PNG action exactly; no hidden new marketplace actions.
  pages=render(bundle);assert [p['family']for p in pages]==['drr','budgets']
  oldplans=[io.get(PLAN+f['plan_id'])for f in old['files']];oldactions={a['id']:a for p in oldplans for a in p['items']};newactions={a['id']:a for f in pages for a in f['actions']}
  assert set(newactions)-set(oldactions)=={action['id']}and set(oldactions)<=set(newactions)
  assert all(digest([newactions[k]])==digest([v])for k,v in oldactions.items())
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
   p=plan(io,DAY,f,index,slot='owner-review18-r1');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256']);markup=buttons(io,p,f['family'])
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
  old.update(bundle=bundle,files=files,corrected_by=ROOT);io.put('china_agent:advertising_artifacts:'+DAY+':v2',old);io.put('china_agent:advertising_delivery:'+DAY+':v1',delivery)
  for f in files:assert io.get(PLAN+f['plan_id'])['report_message_ids']==[1089 if f['family']=='drr' else 1090]
  state.update(status='delivered',completed_at=stamp(),amount_cny=amount,reference_cny=reference,total_actions=sum(f['action_count']for f in files));io.put(ROOT+':journal',state)
  print(json.dumps(dict(status='delivered',message_ids=[1089,1090],funding_proposal_cny=amount,wb_writes=0,telegram_new_messages=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

