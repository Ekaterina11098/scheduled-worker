"""Scoped owner SKU decline diagnosis. Read-only WB/MSK/MPStats; no TG/model."""
import os,json,time,requests
from datetime import datetime,timezone,timedelta
from urllib.parse import urlparse
from analytics.mpstats_probe import discover,unpack_tool,complete_products,sanitize,ProbeError
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:sku_decline:2026-11-22:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();saved=io.get(ROOT+':result')
 if saved and saved.get('status')=='complete':print('Existing complete result; no repeat');return
 v=saved or dict(status='collecting',observed_at=stamp(),errors={},wb_writes=0,model_calls=0,telegram_calls=0)
 if saved is None:assert io.create(ROOT+':result',v)
 def save():io.put(ROOT+':result',v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);h=u.hostname or'';m=method.upper()
  if h==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif h=='mcp.mpstats.io':ok=m=='POST'
  elif h=='api.moysklad.ru':ok=m=='GET'
  elif h=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  elif h=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  elif h=='card.wb.ru':ok=m=='GET'and u.path in('/cards/v4/detail','/cards/v2/detail')
  else:ok=False
  assert ok,'Read scope violation'
  return orig(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def extra(call,checks,known):
  def tool(n,args):return unpack_tool(call('tools/call',dict(name=n,arguments=args)))
  cabinets=checks['lk_wb_cabinets'];initial=[x['id']for x in cabinets if x.get('selected')];assert len(initial)<=1
  assert any(x.get('id')==10026946 and x.get('name')=='VESCHI Гонконг' and x.get('valid')is True for x in cabinets)
  try:
   tool('lk_wb_cabinets',dict(action='select',id=10026946))
   assert [x['id']for x in tool('lk_wb_cabinets',dict(action='list'))if x.get('selected')]==[10026946]
   for name,start,end in [('previous','2026-11-08','2026-11-14'),('current','2026-11-15','2026-11-21')]:
    if name in v:continue
    args=dict(date_from=start,date_to=end,start_row=0,end_row=300)
    data=complete_products(tool,args,sanitize(tool('lk_wb_products',args)))
    body=data['data'];fields=['nm_id','sa_name','name','subject_id','subject_name','orders_count','orders_sum','open_card_count','add_to_cart_count','funnel_orders_count','price_after_discount','price_after_spp','price_spp','fbs_stock','days_in_stock']
    v[name]=dict(period_from=start,period_to=end,observed_at=stamp(),total=body['total'],rows=[{k:r.get(k)for k in fields}for r in body['data']])
    save()
  finally:tool('lk_wb_cabinets',dict(action='select',id=initial[0])if initial else dict(action='reset'))
  return dict(status='received')
 result=discover(os.environ['MPSTATS_API_TOKEN'],read_checks=True,extra_reader=extra)
 v['mpstats_status']=result.get('status');save()
 assert all(k in v for k in('previous','current')),'Weekly data incomplete'
 old={int(r['nm_id']):r for r in v['previous']['rows']};new={int(r['nm_id']):r for r in v['current']['rows']}
 joined=[]
 for nm in old.keys()&new.keys():
  a=old[nm];b=new[nm];joined.append(dict(nm=nm,article=b['sa_name'],cart_loss=(a.get('add_to_cart_count')or 0)-(b.get('add_to_cart_count')or 0),order_loss=(a.get('funnel_orders_count')or 0)-(b.get('funnel_orders_count')or 0)))
 targets={r['nm']for r in sorted(joined,key=lambda x:x['cart_loss'],reverse=True)[:18]if r['cart_loss']>0}|{r['nm']for r in sorted(joined,key=lambda x:x['order_loss'],reverse=True)[:18]if r['order_loss']>0}
 v['targets']=sorted(targets);v['ranking']=sorted(joined,key=lambda x:x['order_loss'],reverse=True);save()
 def stage(key,fn):
  try:v[key]=fn()
  except Exception as e:v['errors'][key]=type(e).__name__+': '+str(e)[:170]
  save()
 stage('prices',lambda:current_prices(io,sorted(targets)))
 def stocks():
  arts=[r['article']for r in v['prices']['rows']];parts=[read_stock(arts[k:k+20],'msk')for k in range(0,len(arts),20)]
  assert all(x['coverage_complete']and x['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'for x in parts)
  return dict(rows=sum([x['rows']for x in parts],[]),observed_at=stamp(),coverage_complete=True,warehouse_id=parts[0]['warehouse_id'])
 stage('stock',stocks);stage('published_stock',lambda:published_stock(io,v['prices'],sorted(targets)))
 def economics():
  baseline=io.get('china_agent:advertising_full_growth:2026-11-22:v1:inputs')
  assert baseline['own']['period_to']=='2026-11-21'
  inp=dict(products=baseline['own'],prices=v['prices'],stock=v['stock'],fx=baseline['fx'])
  return model_rows(inp,io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 stage('economics',economics)
 def buyer():
  errors=[]
  for version in(4,2):
   try:
    r=requests.get('https://card.wb.ru/cards/v'+str(version)+'/detail',params=dict(appType=1,curr='rub',dest=-1257786,spp=30,nm=';'.join(map(str,sorted(targets)))),timeout=(10,35));r.raise_for_status();j=r.json();rows=j.get('products',j.get('data',{}).get('products'))
    assert isinstance(rows,list)and{r['id']for r in rows}==targets
    return dict(observed_at=stamp(),context='Moscow RUB no wallet no personalized account',rows=rows)
   except Exception as e:errors.append(type(e).__name__)
  return dict(status='unavailable',errors=errors,observed_at=stamp())
 stage('buyer',buyer)
 v['status']='complete'if not v['errors']else'partial';v['completed_at']=stamp();save();print(json.dumps(dict(status=v['status'],targets=len(targets),errors=v['errors'])))
if __name__=='__main__':main()
