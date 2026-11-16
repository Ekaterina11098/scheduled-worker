"""Whole-store WB funnel. On-demand reads, ratio of sums, explicit completed periods."""
import re,time,copy
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
PREFIX='Конверсии магазина · запрос меню: '
ROOT='china_agent:shop_funnel:v1:'
DAYROOT='china_agent:shop_funnel_day:v1:'
class PendingShopData(Exception):
 def __init__(self,retry_at,missing):self.retry_at=retry_at;self.missing=missing;super().__init__('Досбор дневной воронки')

def publish_days(w,state):
 if not state.get('complete') or state.get('cabinet')!='token_3' or state.get('currency')!='CNY':raise ValueError('Полнота/валюта общей воронки не подтверждены')
 for field in ('selected','past'):
  rows=state.get('rows')or[]
  if not rows:raise ValueError('Пустая общая воронка')
  p=rows[0].get(field)or{};a=p.get('period_from');b=p.get('period_to')
  if not a or a!=b:continue
  r=dict(aggregate(rows,field,a,b),date=a,status='complete',cabinet='token_3',scope='all_sources_all_products',coverage_complete=True,source_key=state['source_key'],observed_at=state['observed_at'])
  old=w.get(DAYROOT+a)
  if not old or old.get('observed_at','')<r['observed_at']:w.save(DAYROOT+a,r)
def parse(text,today=None):
 m=re.fullmatch(re.escape(PREFIX)+r'(\d{4}-\d{2}-\d{2}) (\d{4}-\d{2}-\d{2})',text)
 if not m:raise ValueError('Неверный запрос общей конверсии магазина')
 a,b=map(date.fromisoformat,m.groups());today=today or datetime.now(ZoneInfo('Europe/Moscow')).date()
 if not 0<=(b-a).days<31 or b>=today:raise ValueError('Выберите от1до31 завершённого дня МСК')
 return a,b
def aggregate(rows,field,first,last):
 seen=set();total=dict(opens=0,carts=0,orders=0)
 if not rows:raise ValueError('WB не вернул товары; пустой ответ не считается нулевой конверсией магазина')
 for r in rows:
  nm=r.get('nm_id');p=r.get(field)or{}
  if type(nm)is not int or nm in seen:raise ValueError('Повтор или отсутствие nmID в общей воронке')
  seen.add(nm)
  if p.get('scope')!='all_sources' or p.get('period_from')!=first or p.get('period_to')!=last:raise ValueError('Охват или период общей воронки не подтверждён')
  for out,key in [('opens','clicks'),('carts','cart_count'),('orders','orders')]:
   v=p.get(key)
   if type(v)is not int or v<0:raise ValueError('Неполные счётчики общей воронки')
   total[out]+=v
 total.update(open_cart_pct=100*total['carts']/total['opens']if total['opens']else None,cart_order_pct=100*total['orders']/total['carts']if total['carts']else None,open_order_pct=100*total['orders']/total['opens']if total['opens']else None,product_count=len(seen),period_from=first,period_to=last)
 return total
def collect(w,first,last,reports=None,sleeper=time.sleep):
 from china_wb_evidence import Reports,ROOT as EVIDENCE
 a,b=date.fromisoformat(first),date.fromisoformat(last)
 days=[str(a+timedelta(days=i))for i in range((b-a).days+1)]
 required=sorted({str(date.fromisoformat(d)-timedelta(days=n))for d in days for n in (0,1,7)})
 reports=reports or Reports(w);cache={};reads=0
 for day in reversed(required):
  r=w.get(DAYROOT+day)
  if not r:
   # Reuse exact full-day sources, including the later response's past revision.
   for s in (day,str(date.fromisoformat(day)+timedelta(days=1))):
    state=w.get(EVIDENCE+'funnel:'+s+':'+s)
    if state and state.get('complete'):publish_days(w,state)
   r=w.get(DAYROOT+day)
  if not r:
   if reads>=1:raise PendingShopData((datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat(),[d for d in required if not w.get(DAYROOT+d)])
   state=reports.funnel(day,day);reads+=1
   if not state.get('complete'):
    if state.get('retry_at') or not str(state.get('status','')).startswith('WB_HTTP'):
     raise PendingShopData(state.get('retry_at')or(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat(),[day])
    raise ValueError('WB: '+str(state.get('status')))
   publish_days(w,state);r=w.get(DAYROOT+day)
  if not r or r.get('status')!='complete' or r.get('cabinet')!='token_3' or r.get('scope')!='all_sources_all_products' or r.get('coverage_complete')is not True or any(type(r.get(k))is not int or r[k]<0 for k in ('opens','carts','orders')):raise ValueError('Неполные дневные счётчики '+day)
  cache[day]=r
 def window(offset):
  rs=[cache[str(date.fromisoformat(d)-timedelta(days=offset))]for d in days]
  r={k:sum(v[k]for v in rs)for k in ('opens','carts','orders')}
  r.update(period_from=rs[0]['date'],period_to=rs[-1]['date'],product_count=max(v['product_count']for v in rs),product_count_basis='maximum_daily',observed_at=max(v['observed_at']for v in rs))
  r.update(open_cart_pct=100*r['carts']/r['opens']if r['opens']else None,cart_order_pct=100*r['orders']/r['carts']if r['carts']else None,open_order_pct=100*r['orders']/r['opens']if r['opens']else None)
  return r
 daily=[dict(cache[d],previous=cache[str(date.fromisoformat(d)-timedelta(days=1))],week=cache[str(date.fromisoformat(d)-timedelta(days=7))])for d in days]
 out=dict(status='complete',version=2,cabinet='token_3',scope='all_sources_all_products',coverage_complete=True,period_from=first,period_to=last,selected=window(0),previous=window(1),week=window(7),daily=daily,source_keys=sorted({r['source_key']for r in cache.values()}),source_observed_at=sorted({r['observed_at']for r in cache.values()}),observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,model_calls=0)
 w.save(ROOT+first+':'+last,out);return out
def answer(data):
 def num(v):return 'н/д'if v is None else str(round(v,2)).replace('.',',')
 text='Конверсии магазина · '+data['period_from']+' — '+data['period_to']+' · полные дни МСК. Общая воронка WB, все источники и все товары ответа; пагинация проверена.\n\n'
 text+='| Период | Открытия | Корзины | Открытия→корзины,% | Заказы | Корзины→заказы,% | Открытия→заказы,% |\n|---|---|---|---|---|---|---|\n'
 for k,label in [('selected','Выбранный'),('previous','Сдвиг на день назад'),('week','Сдвиг на неделю назад')]:
  r=data[k];text+='| '+label+' '+r['period_from']+'—'+r['period_to']+' | '+' | '.join(num(r[f])for f in ['opens','carts','open_cart_pct','orders','cart_order_pct','open_order_pct'])+' |\n'
 text+='\n| Дата | Открытия | Корзины | Заказы | CR,% | CR вчера,% | CR неделю назад,% |\n|---|---|---|---|---|---|---|\n'
 cr=lambda r:100*r['orders']/r['opens']if r['opens']else None
 for r in data['daily']:text+='| '+r['date']+' | '+' | '.join(num(r[k])for k in ('opens','carts','orders'))+' | '+' | '.join(num(cr(v))for v in (r,r['previous'],r['week']))+' |\n'
 text+='\nПроценты рассчитаны по суммам, не как среднее процентов товаров. Открытия — не уникальные посетители. Заказы — общая воронка, не рекламные заказы и не выкупы. Отношение корзин к заказам не является доказанной когортой покупателей. При нулевом знаменателе — н/д. WB может запаздывать до2часов.\nИсточники получены: '+', '.join(sorted({data[k]['observed_at']for k in ['selected','previous','week']}))+'.'
 return text
def run(w,job,text):
 from china_analytic_dialog import reading
 a,b=parse(text)
 with reading():data=collect(w,str(a),str(b))
 text=answer(data)
 from china_table_png import blocks,render
 from china_menu_analytics import freeze
 blobs=[blob for kind,content in blocks(text)if kind=='table'for blob in render(*content)]
 if not blobs:raise ValueError('Общий PNG не сформирован')
 freeze(w,job,text,blobs)
 return text

