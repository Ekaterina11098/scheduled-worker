import json,copy,time,io as bio,textwrap,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from PIL import Image,ImageDraw,ImageFont
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_midday26_buttons:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();auth=io.get(ROOT+':approval');assert auth['status']=='approved_for_publication_only' and auth['owner_id']==5122667182 and not auth['wb_execution_authorized'];validate_identity(Cache(),WB());assert not io.get(ROOT+':delivery'),'Inspect delivery; never repeat send'
 state=dict(status='preflight',started_at=now(),actions=[],blocked=[],checks=[],wb_writes=0,telegram_calls=0);assert io.create(ROOT+':delivery',state)
 def save():io.put(ROOT+':delivery',copy.deepcopy(state))
 original=requests.sessions.Session.request
 def guard(s,m,url,*a,**kw):
  u=urlparse(url);m=m.upper();ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH') and u.path.startswith('/rest/v1/')
  if u.hostname=='advert-api.wildberries.ru':ok=m=='GET' and u.path in('/api/advert/v2/adverts','/api/advert/v1/config') or m=='POST' and u.path=='/api/advert/v1/bids/min'
  if u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET' and u.path=='/api/v2/list/goods/filter'
  if u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST' and u.path=='/api/v3/stocks/2126188'
  if u.hostname=='api.moysklad.ru':ok=m=='GET' and u.path.startswith('/api/remap/1.2/')
  if u.hostname=='api.telegram.org':ok=m=='POST' and u.path.rsplit('/',1)[-1]=='sendPhoto' and str(kw.get('data',{}).get('chat_id'))=='-1004342917488'
  assert ok,'No WB writes or unrelated Telegram calls';return original(s,m,url,*a,**kw)
 requests.sessions.Session.request=guard
 def req(path,body=None):
  time.sleep(1.2);r=requests.request('POST' if body is not None else 'GET','https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50);r.raise_for_status();return r.json()
 try:
  ids=sorted({x['campaign_id'] for x in auth['actions']});cs=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids)))['adverts'];states={c['id']:c for c in cs};assert set(states)==set(ids)
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
  inp=io.get('china_agent:advertising_full_growth:2026-11-26:v1:inputs:midday');assert inp['status']=='complete'
  rr=requests.get('https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter',headers={'Authorization':io.token},params={'limit':1000,'offset':0},timeout=50);rr.raise_for_status();goods=rr.json()['data']['listGoods'];assert len(goods)<1000;prices={g['nmID']:g for g in goods}
  from china_moysklad_read import read_stock
  st=read_stock([x['article'] for x in auth['actions']]);assert st['coverage_complete'];stocks={x['article']:x for x in st['rows']}
  for a0 in auth['actions']:
   a=copy.deepcopy(a0);c=states[a['campaign_id']]
   try:
    assert c['status']==9 and c['currency']=='CNY' and c['bid_type']=='manual' and c['settings']['payment_type']=='cpc'
    n=next(x for x in c['nm_settings'] if x['nm_id']==a['nm_id']);assert n['bids_kopecks'].get(a['placement'])==a['old_minor'],'Current bid differs; do not publish stale action'
    typ='search' if a['placement']=='search' else 'recommendation';j=req('/api/advert/v1/bids/min',dict(advert_id=c['id'],nm_ids=[a['nm_id']],payment_type='cpc',placement_types=[typ]));v=[z['value'] for x in j['bids'] if x['nm_id']==a['nm_id'] for z in x['bids'] if z['type']==typ and z['currency']=='CNY'];assert len(v)==1 and v[0]<=a['target_minor']<=cfg['cpcMaxBid'] and a['target_minor']%cfg['cpcStep']==0,'Minimum or step invalid'
    pr=prices[a['nm_id']];assert pr['currencyIsoCode4217']=='CNY' and pr['vendorCode']==a['article'];vals={z['discountedPrice'] for z in pr['sizes']};assert len(vals)==1;price=next(iter(vals));e=copy.deepcopy(inp['economics']['rows'][str(a['nm_id'])]);ss=stocks[a['article']];cost=ss['price']/100;fx=e['fx_rub_per_cny'];e['expected_margin_before_ads_cny']+=e['buyout']*((price-e['seller_price_cny'])*(1-(e['commission_pct']+e['tax_pct']+e['payment_reserve_pct'])/100)-(cost-e['own_cogs_rub'])/fx);e.update(seller_price_cny=price,own_cogs_rub=cost,stock_free=ss['stock']-ss['reserve']);assert price>0
    if a['direction']=='raise':
     review=io.get('china_agent:advertising_midday_completed:2026-11-26:v1')['review']; cc=next(z for z in review['campaigns'] if z['id']==a['campaign_id']); metrics=next(z for z in cc['focus'] if z['nm']==a['nm_id'])['period'];cpa=metrics['spend']/metrics['orders']*a['target_minor']/a['old_minor'];stress=e['expected_margin_before_ads_cny']-max(0,35-e['logistics_cny']);assert stress>cpa*1.25 and cpa*metrics['orders']/metrics['amount']*100<=8 and e['stock_free']>0,'Stress economics do not support raise'
     ev=dict(e,cabinet='token_3',currency='CNY',article=a['article'],observed_at=now(),period_from='2026-11-23',period_to='2026-11-25',decision_days=['2026-11-23','2026-11-24','2026-11-25'],metrics=metrics,price_cny=price,stress_margin_before_ads_cny=stress,modeled_cpa_same_cr=cpa,manual_strategy_proposal=True,source_key='china_agent:advertising_midday_completed:2026-11-26:v1',preliminary=True)
     a['growth_evidence']=ev
     from china_advertising_growth import validate_raise
     validate_raise(io,a,c)
    a['preflight_economics']=e;state['actions'].append(a);state['checks'].append(dict(id=a['id'],minimum=v[0],before=c,price=price,economics=e,observed_at=now()));save()
   except Exception as ex:state['blocked'].append(dict(id=a['id'],article=a['article'],reason=type(ex).__name__+': '+str(ex)[:240]));save()
  assert state['actions'],'No verified actions to publish'
  rows=copy.deepcopy(auth['preview']['rows']);selected={a['campaign_id']:a for a in state['actions']}
  for row in rows:
   if row['id'] in {a['campaign_id'] for a in auth['actions']} and row['id'] not in selected:row['recommendation']='Изменение из предварительного варианта не прошло проверку. Текущие ставки сохранить.'
  font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';F=ImageFont.truetype(font,24);B=ImageFont.truetype(bold,29);W=1600
  rendered=[]
  for row in rows:
   lines=textwrap.wrap(row['recommendation'],width=76);rendered.append((row,lines,max(110,len(lines)*33+25)))
  im=Image.new('RGB',(W,260+sum(h+10 for _,_,h in rendered)+100),'#eaf4ee');draw=ImageDraw.Draw(im);draw.rectangle((0,0,W,170),fill='#176847');draw.text((30,25),'Китай · промежуточный отчёт · 26.11.2026',font=B,fill='white');draw.text((30,78),'Цель ДРР 8% · ставки и минимумы проверены '+now()[11:16]+' UTC',font=F,fill='white');draw.text((30,123),'Повысить: '+str(sum(a['direction']=='raise'for a in state['actions']))+' · Снизить: '+str(sum(a['direction']=='reduce'for a in state['actions']))+' · Без пополнений и изменения цен',font=F,fill='white');y=195
  for row,lines,h in rendered:
   draw.rounded_rectangle((15,y,W-15,y+h),radius=12,fill='white');draw.text((30,y+12),str(row['id']),font=B,fill='#176847');draw.text((30,y+57),f"Расход {row['spend']:.2f} CNY",font=F,fill='#222222')
   for k,line in enumerate(lines):draw.text((390,y+12+33*k),line,font=F,fill='#222222')
   y+=h+10
  draw.text((30,y+20),'Только проверенные действия этого отчёта. Исполнение — после подтверждения кнопкой.',font=F,fill='#176847');buff=bio.BytesIO();im.crop((0,0,W,y+85)).save(buff,format='PNG');png=buff.getvalue()
  from china_daily_ad_actions import plan,bind
  from china_report_buttons import prepare
  from china_loss_control import CHAT,PLAN
  f=dict(family='drr',kind='drr:001',page=1,total=1,actions=state['actions']);p=plan(io,'2026-11-26',f,0,slot='owner-verified-codex5');f.update(plan_id=p['plan_id'],plan_sha256=p['plan_sha256']);keyboard=prepare(io,p,'drr');assert keyboard
  state.update(status='sending',plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],keyboard=keyboard,preflight_at=now());save()
  try:
   rr=requests.post('https://api.telegram.org/bot'+io.bot+'/sendPhoto',data=dict(chat_id=CHAT,caption='Китай · промежуточный отчёт · 26.11.2026. Проверено '+str(len(state['actions']))+' изменений ставок. Подтвердите кнопкой. Цены и бюджеты не меняем.',reply_markup=json.dumps(keyboard,ensure_ascii=False)),files={'photo':('report.png',png,'image/png')},timeout=60);v=rr.json();assert rr.ok and v.get('ok');receipt=v['result'];assert receipt['chat']['id']==CHAT and receipt.get('reply_markup')==keyboard
  except Exception:state.update(status='uncertain');save();raise
  state.update(status='sent',telegram_calls=1,message_id=receipt['message_id'],receipt=receipt);save();bind(io,f,receipt);assert io.get(PLAN+p['plan_id'])['report_message_ids']==[receipt['message_id']];state.update(status='delivered',completed_at=now());save();print(json.dumps(dict(status='delivered',message_id=receipt['message_id'],actions=len(state['actions']),blocked=state['blocked'],wb_writes=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()


