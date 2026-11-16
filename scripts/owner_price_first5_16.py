"""Owner16Nov: nine own-SKU price reviews, one combined report edit, no WB writes/model."""
import copy,hashlib,json,os
from datetime import datetime,date,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import requests
ROOT='china_agent:owner_price_first5:2026-11-16:v1'
DAY='2026-11-16';MID=1057;JOB=335;CHAT=-1004342917488
NINE={'1473243440','1556488188','1473242764','1556488187','1473242762','1556488194','1473242569','1473244000','1473246048'}

def calculate(review,inputs):
 from china_price_economic_target import choose_target
 out=copy.deepcopy(review)
 models=next(r['payload']for r in inputs if 'advertising_full_growth'in r['cache_key'])
 history=next(r['payload']for r in inputs if 'demand_watch'in r['cache_key'])
 found=set()
 for p in out['products']:
  nm=p['nm_id']
  if nm not in NINE:continue
  assert p['full_days']>=4 and p['result']['status']=='rollback_review'
  assert p['linked_context']['status']=='membership_changed'
  m=models[nm];c=history[nm]['last_price_change'];assert m['fx_date']==DAY
  assert p['after_price']==m['seller_price_cny'] and p['before_price']==c['before_price']['current_cny']
  p['economic_target']=choose_target(c['before_price'],c['after_price'],p['before'],p['after'],buyout_probability=p['buyout_percent']/100,retention=1-(m['commission_pct']+m['tax_pct']+m.get('payment_reserve_pct',3))/100,cost=m['own_cogs_rub'],dispatch=m['logistics_cny']*m['fx_rub_per_cny']+m['handling_rub'],fx=m['fx_rub_per_cny'])
  p['membership_change_not_a_veto']=True
  found.add(nm)
 assert found==NINE
 out['owner_membership_revision']=dict(source=ROOT,reviewed=9,execution_authorized=False)
 return out

def main():
 from china_advertising_state import AdvertisingIO
 from china_cloud_cost_control import Cache,stamp
 from china_morning_readiness import current_prices,published_stock
 from china_moysklad_read import read_stock
 from china_buyer_price_forecast import build,forecast
 from china_price_brief import lowering,price
 from china_price_delivery import rows
 from china_price_buttons import prepare
 from china_table_png import render
 assert datetime.now(ZoneInfo('Europe/Moscow')).date().isoformat()==DAY,'Dated owner instruction expired'
 io=AdvertisingIO();c=Cache()
 old=c.get(ROOT+':delivery')
 if old:raise RuntimeError('Existing report revision journal; no automatic replay')
 owner=c.get('china_agent:shared_memory:v1:work:note:owner-price-membership-no-veto-20261116')
 assert owner['status']=='active' and owner['author_id']==5122667182
 source=c.get('china_agent:owner_price_nine:2026-11-16:v1:inputs');review=c.get(source['source_key']);assert review['report_date']==DAY
 original=c.get('china_agent:owner_price_nine:2026-11-16:v1:prepared')
 binding=c.get('china_agent:price_report_message:v1:'+str(MID))
 assert binding['status']=='revoked' and binding.get('revoked_reason')=='first_decrease_max5' and binding['report_job_id']==JOB and binding['report_sha256']==original['answer_sha256']
 jobs=io.db('business_agent_jobs?agent_id=eq.china&id=gte.'+str(JOB)+'&select=id,status,answer,request_text,tool_trace&order=id.asc&limit=20')
 assert len(jobs)==1 and jobs[0]['id']==JOB and jobs[0]['status']=='done' and jobs[0]['answer']==original['answer'],'New request or confirmation; refresh report race review'
 updated=calculate(review,source['inputs']);catalogue=c.get('china_agent:prices:v1')
 up=[r for r in rows(original['answer'])if r[0]=='Повышение'];assert len(up)==3
 down=lowering(updated,DAY,catalogue);assert len(down)==4
 alloffers=up+[['Снижение',a,o+' → '+n+' ¥','']for a,o,n in down]
 by_article={r['vendorCode']:r for r in catalogue['rows']}
 ids=[int(by_article[r[1]]['nmID'])for r in alloffers]
 assert len(set(ids))==7 and not set(ids)&{1473245494,1473245510}
 live=current_prices(io,ids);stocks=read_stock([r[1]for r in alloffers]);wb=published_stock(io,live,ids)
 models={p['nm_id']:p for p in updated['products']}
 for action,article,change,buyer in alloffers:
  nm=str(by_article[article]['nmID']);oldprice=Decimal(change.split('→')[0].strip().replace(',','.'))
  p=[x for x in live['rows']if str(x['nm_id'])==nm];s=[x for x in stocks['rows']if x['article'].casefold()==article.casefold()]
  assert len(p)==1 and Decimal(str(p[0]['seller_price']))==oldprice,'Current price changed'
  assert len(s)==1 and s[0]['stock']-s[0]['reserve']>0 and wb['amounts'].get(nm,0)>0,'Availability changed'
  if action=='Снижение':
   assert abs(s[0]['price']/100-models[nm]['own_cogs_rub'])<=.02,'Own COGS changed'
   target=models[nm]['economic_target'];row=by_article[article]
   assert Decimal(str(target['discount']))==Decimal(str(row['discount'])),'Do not alter seller discount'
 raw=source['buyer'];buyer=build(raw['rows'],raw,catalogue,date.fromisoformat(DAY));assert buyer['status']=='available'
 blocks=[]
 for action,article,change,_ in alloffers:
  oldprice,newprice=[v.strip().replace(',','.')for v in change.replace('¥','').split('→')]
  nm=str(by_article[article]['nmID']);a=forecast(buyer,nm,article,oldprice,oldprice,DAY);b=forecast(buyer,nm,article,oldprice,newprice,DAY)
  assert a is not None and b is not None,'Buyer forecast missing'
  blocks.append(action+' · '+article+' Продавец: '+price(oldprice)+' → '+price(newprice)+' ¥\nПокупатель: '+format(a,',').replace(',',' ')+' → '+format(b,',').replace(',',' ')+' ₽')
 answer='\n\n'.join(blocks);offers=rows(answer);assert len(offers)==7
 scope=hashlib.sha256(answer.encode()).hexdigest()
 markup,registry=prepare(answer,offers,JOB,DAY,binding['expires_at'])
 pics=render(['Действие','Арт','Цена продавца','Цена покупателя (новая — прогноз)'],offers,title='Китай · рекомендации по ценам · 16.11.2026')
 if isinstance(pics,bytes):pics=[pics]
 assert len(pics)==1,'Combined price PNG split unexpectedly'
 pic=pics[0]['bytes']if isinstance(pics[0],dict)else pics[0]
 c.put(ROOT+':review',updated)
 c.put(ROOT+':preflight',dict(prices=live,stock=stocks,published_stock=wb,observed_at=stamp(),wb_writes=0))
 c.put(ROOT+':prepared',dict(answer=answer,answer_sha256=scope,offers=offers,reply_markup=markup,button_registry=registry,png_sha256=hashlib.sha256(pic).hexdigest(),selection_count=7,buyer_basis=buyer,execution_authorized=False))
 # Recheck pending human work immediately before changing any binding.
 assert len(io.db('business_agent_jobs?agent_id=eq.china&id=gt.'+str(JOB)+'&select=id&limit=1'))==0
 oldreg=original['button_registry'];prior=c.get(oldreg['key']);assert prior['status']=='revoked' and 'first decrease' in prior.get('revoked_reason','')
 c.put(ROOT+':previous_binding',binding);c.put(ROOT+':previous_buttons',prior)
 c.put(oldreg['key'],dict(prior,status='superseded',superseded_by=registry['key']))
 c.put(registry['key'],dict(registry['payload'],status='preparing'))
 c.put('china_agent:price_report_message:v1:'+str(MID),dict(binding,status='revising',revision_key=ROOT))
 job=io.db('business_agent_jobs?agent_id=eq.china&id=eq.'+str(JOB)+'&status=eq.done','PATCH',dict(answer=answer),'return=representation')
 assert len(job)==1
 if not c.create(ROOT+':delivery',dict(status='editing',message_id=MID,answer_sha256=scope,started_at=stamp(),wb_writes=0)):raise RuntimeError('Report edit already claimed')
 me=io.tg('getMe',{});assert me['id']==8780468043
 media=dict(type='photo',media='attach://photo',caption='Китай · цены · 16.11.2026. Повышение: 3. Снижение: 4. Подтвердите кнопкой под отчётом. Цена покупателя — прогноз.')
 try:
  response=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=CHAT,message_id=MID,media=json.dumps(media,ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('prices.png',pic,'image/png')},timeout=60)
  reply=response.json()
 except Exception:
  c.put(ROOT+':delivery',dict(status='uncertain',message_id=MID,at=stamp(),wb_writes=0));raise RuntimeError('Telegram edit uncertain; no replay')from None
 if not response.ok or reply.get('ok')is not True:
  c.put(ROOT+':delivery',dict(status='rejected',message_id=MID,http_status=response.status_code,description=reply.get('description'),at=stamp(),wb_writes=0));raise RuntimeError('Telegram rejected edit: '+str(response.status_code))
 receipt=reply['result'];assert receipt['message_id']==MID and receipt['chat']['id']==CHAT and receipt.get('photo')
 c.put(registry['key'],registry['payload'])
 c.put('china_agent:price_report_message:v1:'+str(MID),dict(binding,status='sent',report_sha256=scope,selection_count=9,receipt_key=ROOT+':delivery',revision_key=ROOT))
 policy=c.get('china_agent:price_review_policy:v1')or{}
 policy.update(scope='price_recommendations',changed_membership_veto=False,owner_source='codex_owner_2026-11-16',source_key='china_agent:shared_memory:v1:work:note:owner-price-membership-no-veto-20261116',updated_at=stamp(),grants_action_permission=False)
 policy['first_decrease_max_percent']=5
 c.put('china_agent:price_review_policy:v1',policy)
 c.put(source['source_key'],updated)
 c.put(ROOT+':delivery',dict(status='edited',message_id=MID,job_id=JOB,receipt=receipt,answer_sha256=scope,button_registry_key=registry['key'],selection_count=9,ready_decreases=4,completed_at=stamp(),wb_writes=0,model_calls=0))
 assert c.get('china_agent:price_report_message:v1:'+str(MID))['report_sha256']==scope
 print(json.dumps(dict(status='edited',message_id=MID,ready_decreases=6,selection_count=9,wb_writes=0,model_calls=0)))

if __name__=='__main__':
 from urllib.parse import urlparse
 original=requests.sessions.Session.request
 def guarded(self,method,url,*args,**kwargs):
  parsed=urlparse(url);host=parsed.hostname or'';path=parsed.path;method=method.upper()
  if host.endswith('.wildberries.ru'):
   assert (host=='discounts-prices-api.wildberries.ru'and method=='GET'and path=='/api/v2/list/goods/filter')or(host=='marketplace-api.wildberries.ru'and method=='POST'and path=='/api/v3/stocks/2126188'),'WB mutation forbidden'
  elif host=='api.telegram.org':assert path.rsplit('/',1)[-1]in('getMe','editMessageMedia'),'Unexpected Telegram action'
  elif host=='api.moysklad.ru':assert method=='GET','MoySklad write forbidden'
  else:assert host==urlparse(os.environ['SUPABASE_URL']).hostname and path.startswith('/rest/v1/'),'Unexpected network request'
  return original(self,method,url,*args,**kwargs)
 requests.sessions.Session.request=guarded
 try:main()
 finally:requests.sessions.Session.request=original

