"""Owner requested13-SKU price investigation: bounded reads, private output, no writes to WB/TG/models."""
import os,json,time
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_price13_review:2026-11-16:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();scope=c.get(ROOT+':scope')or{}
 assert scope.get('owner_id')==5122667182 and scope.get('wb_writes')==0 and scope.get('status')=='authorized_read_only'
 ids=scope['nm_ids'];articles=scope['articles'];assert len(ids)==13 and len(set(ids))==13 and len(articles)==13
 if not c.create(ROOT+':claim',dict(status='collecting',at=stamp(),wb_writes=0)):raise ValueError('Already claimed: inspect result; do not repeat collection blindly')
 v=dict(status='collecting',cabinet='token_3',observed_at=stamp(),errors={},wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 def save():c.put(ROOT, json.loads(json.dumps(v)))
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper();p=u.path
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=p.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=method=='GET'and p=='/api/v2/list/goods/filter'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=method=='POST'and p=='/api/v3/stocks/2126188'and set(kw.get('json',{}))=={'chrtIds'}
  elif u.hostname=='api.moysklad.ru':ok=method=='GET'and p.startswith('/api/remap/1.2/')
  elif u.hostname=='dp-calendar-api.wildberries.ru':ok=method=='GET'and p in('/api/v1/calendar/promotions','/api/v1/calendar/promotions/nomenclatures')
  elif u.hostname=='mcp.mpstats.io':
   b=kw.get('json')or{};name=(b.get('params')or{}).get('name');ok=method=='POST'and p=='/mcp'and(b.get('method')in('initialize','notifications/initialized','tools/list')or b.get('method')=='tools/call'and name in('account_limits','lk_wb_cabinets','lk_wb_products'))
  else:ok=False
  assert ok,'Read-only investigation scope rejected '+method+' '+(u.hostname or'')+p
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def read(name,fn):
  try:v[name]=fn()
  except Exception as e:v['errors'][name]=type(e).__name__+': '+str(e)[:350]
  save()
 def get(url,params=None):
  time.sleep(.7);r=requests.get(url,params=params,headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(10,60));r.raise_for_status();return r.json()
 try:
  validate_identity(c,WB())
  def prices():
   rows=[]
   for nm in ids:
    part=get('https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter',dict(limit=1000,offset=0,filterNmID=nm))['data']['listGoods']
    assert len(part)==1 and part[0]['nmID']==nm and part[0]['currencyIsoCode4217']=='CNY'
    rows+=part
   return dict(rows=rows,observed_at=stamp(),coverage_complete=True)
  read('prices',prices)
  from china_moysklad_read import read_stock
  read('msk_stock',lambda:read_stock(articles))
  if v.get('prices'):
   from china_morning_readiness import published_stock
   p=dict(rows=[dict(nm_id=r['nmID'],size_ids=[s['sizeID']for s in r['sizes']])for r in v['prices']['rows']])
   read('published_stock',lambda:published_stock(type('IO',(),dict(token=os.environ['WB_TOKEN_3']))(),p,ids))
  def products():
   from analytics.mpstats_probe import discover
   from analytics.mpstats_gaps import execute_reads
   observations=[];tasks=[dict(cabinet='token_3',tool='lk_wb_products',key='owner-price13:2026-11-13:2026-11-15',priority=80,arguments=dict(date_from='2026-11-13',date_to='2026-11-15',start_row=0,end_row=1000))]
   def persist(cabinet,obs):
    if cabinet=='token_3'and obs.get('scope_verified')is True and obs.get('status')=='received':observations.append(obs)
   def extra(call,checks,known):return execute_reads(call,checks,known,tasks,{},persist,max_requests=1)
   discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
   assert len(observations)==1
   body=observations[0]['data']['data'];rows=body['data'];assert body.get('need_update')==0 and body.get('total')==len(rows)
   selected=[r for r in rows if int(r['nm_id'])in ids];assert len(selected)==13
   return dict(rows=selected,observed_at=stamp(),period_from='2026-11-13',period_to='2026-11-15',coverage_complete=True,source_total_rows=len(rows))
  read('buyer_products',products)
  def promotions():
   raw=get('https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions',dict(startDateTime='2026-11-12T00:00:00Z',endDateTime='2026-11-17T23:59:59Z',allPromo='false'))
   promos=raw.get('data',{}).get('promotions');assert isinstance(promos,list)
   out=dict(observed_at=stamp(),promotions=promos,matching_products=[],unavailable=[],complete=len(promos)<=20)
   for promo in promos[:20]:
    pid=promo['id']
    try:
     data=get('https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/nomenclatures',dict(promotionID=pid,inAction='true',limit=1000,offset=0))
     rows=data.get('data',{}).get('nomenclatures');assert isinstance(rows,list)and len(rows)<1000
     out['matching_products'] +=[dict(promotion_id=pid,row=r)for r in rows if int(r.get('id',r.get('nmID',r.get('nm_id',0))))in ids]
    except Exception as ex:out['unavailable'].append(dict(promotion_id=pid,reason=type(ex).__name__+': '+str(ex)[:180]));out['complete']=False
   return out
  read('promotions',promotions)
  v.update(status='complete'if not v['errors']else'partial',completed_at=stamp());save()
  print(json.dumps(dict(status=v['status'],errors=v['errors'],prices=len(v.get('prices',{}).get('rows',[])),buyer_rows=len(v.get('buyer_products',{}).get('rows',[])),wb_writes=0,telegram_calls=0,model_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
