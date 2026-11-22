"""Owner return-review preflight. No WB changes, TG or model."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:return_review:2026-11-22:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();scope=io.get(ROOT+':scope');assert scope['status']=='authorized_read_only'and scope['owner_id']==5122667182
 old=io.get(ROOT+':fresh')
 if old and old.get('status')=='complete':print('Complete already, no duplicate');return
 v=old or dict(status='collecting',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if old is None:assert io.create(ROOT+':fresh',v)
 orig=requests.sessions.Session.request
 def guard(s,m,url,*args,**kw):
  u=urlparse(url);h=u.hostname;m=m.upper()
  if h==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif h=='advert-api.wildberries.ru':ok=m=='GET'and u.path in('/adv/v1/promotion/count','/api/advert/v2/adverts','/api/advert/v1/config')or m=='POST'and u.path=='/api/advert/v1/bids/min'
  elif h=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  elif h=='marketplace-api.wildberries.ru':ok=m=='POST'and u.path=='/api/v3/stocks/2126188'
  elif h=='api.moysklad.ru':ok=m=='GET'
  else:ok=False
  assert ok,'Read-only preflight scope violation'
  return orig(s,m,url,*args,**kw)
 requests.sessions.Session.request=guard
 def save():io.put(ROOT+':fresh',v)
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as e:v['errors'][k]=type(e).__name__+': '+str(e)[:130]
  save()
 def ad(path,body=None):
  time.sleep(1.0);r=requests.request('GET'if body is None else'POST','https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=(10,50));r.raise_for_status();return r.json()
 def campaigns():
  count=ad('/adv/v1/promotion/count');ids=set(scope['campaign_ids'])
  for group in count.get('adverts',[]):
   if group.get('status')in(9,11):ids.update(x['advertId']for x in group.get('advert_list',[]))
  assert len(ids)<=100
  rows=ad('/api/advert/v2/adverts?ids='+','.join(map(str,sorted(ids)))+'&owner_read='+str(time.time_ns()))['adverts']
  assert {r['id']for r in rows}==ids and all(r['currency']=='CNY'for r in rows)
  return dict(observed_at=now(),adverts=rows)
 stage('campaigns',campaigns)
 stage('prices',lambda:current_prices(io,scope['nms']))
 def stock():
  arts=[r['article']for r in v['prices']['rows']];parts=[]
  for start in range(0,len(arts),20):
   key=ROOT+':stock:'+str(start);part=io.get(key)
   if part is None:
    part=read_stock(arts[start:start+20],'msk');assert io.create(key,part)
   assert part['coverage_complete']and part['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
   parts.append(part)
  return dict(rows=sum([x['rows']for x in parts],[]),observed_at=now(),coverage_complete=True,warehouse_id=parts[0]['warehouse_id'])
 stage('stock',stock);stage('published_stock',lambda:published_stock(io,v['prices'],scope['nms']))
 def econ():
  base=io.get('china_agent:advertising_full_growth:2026-11-22:v1:inputs')
  return model_rows(dict(products=base['own'],prices=v['prices'],stock=v['stock'],fx=base['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 stage('economics',econ)
 def minima():
  base=io.get('china_agent:advertising_full_growth:2026-11-22:v1:inputs');subjects={r['nm_id']:r.get('subject_id')for r in base['own']['rows']};chosen={}
  for c in v['campaigns']['adverts']:
   if c['status']!=9 or c['id']==42088552:continue
   zones=[z for z,on in c['settings']['placements'].items()if on]
   if len(zones)!=1:continue
   zone=zones[0]
   for n in c['nm_settings']:
    subject=subjects.get(n['nm_id'])
    if subject is not None:chosen.setdefault((subject,zone),(c['id'],n['nm_id']))
  out=[]
  for(sub,z),(cid,nm)in chosen.items():
   out.append(dict(subject_id=sub,placement=z,campaign_id=cid,representative_nm=nm,observed_at=now(),quote=ad('/api/advert/v1/bids/min',dict(advert_id=cid,nm_ids=[nm],payment_type='cpc',placement_types=['search'if z=='search'else'recommendation']))))
  return out
 stage('minimums',minima)
 v['status']='complete'if not v['errors']else'partial';v['completed_at']=now();save();print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()
