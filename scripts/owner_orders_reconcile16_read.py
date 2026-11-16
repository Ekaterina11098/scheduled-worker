"""Exact three-date order reconciliation, RID/time/status/money. Read only, no monitor/model/TG."""
import os,json,time
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_orders_reconcile:2026-11-16:v1'
MSK=ZoneInfo('Europe/Moscow');CUT=datetime(2026,11,16,21,tzinfo=MSK)
FBS_FIELDS=('id','rid','orderUid','createdAt','article','nmId','chrtId','warehouseId','isZeroOrder','price','salePrice','currencyCode','convertedPrice','convertedCurrencyCode')
STATS_FIELDS=('date','lastChangeDate','supplierArticle','nmId','srid','isCancel','cancelDate','warehouseName','warehouseType','orderType','barcode','totalPrice','discountPercent','spp','priceWithDisc','finishedPrice','gNumber','sticker')
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 c=Cache();validate_identity(c,WB());assert datetime.now(MSK)>=CUT and datetime.now(MSK).date()==CUT.date()
 if not c.create(ROOT+':claim',dict(status='reading',at=stamp(),wb_writes=0)):raise RuntimeError('Existing immutable reconciliation claim; inspect, do not replay')
 out=dict(status='collecting',cut_msk=CUT.isoformat(),cabinet='token_3',created_at=stamp(),fbs={},statistics={},errors={},wb_writes=0,telegram_calls=0,model_calls=0,grants_action_permission=False)
 def save():c.put(ROOT,json.loads(json.dumps(out)))
 def get(host,path,params=None):
  r=requests.get('https://'+host+path,params=params,headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(10,60));r.raise_for_status();return r.json()
 new=get('marketplace-api.wildberries.ru','/api/v3/orders/new')['orders'];assert isinstance(new,list)
 # One bounded paginated read per date; keep RID and original timestamps/money.
 for offset in(0,1,7):
  end=CUT-timedelta(days=offset);start=end.replace(hour=0);rows={};cursor=0
  for page in range(3):
   body=get('marketplace-api.wildberries.ru','/api/v3/orders',dict(limit=1000,next=cursor,dateFrom=int(start.timestamp()),dateTo=int(end.timestamp())));part=body['orders'];assert isinstance(part,list)
   for r in part:rows[r['id']]=r
   nxt=body.get('next')
   if not part or not nxt:break
   assert nxt!=cursor;cursor=nxt;time.sleep(.5)
  else:raise RuntimeError('FBS pagination incomplete')
  for r in new:rows[r['id']]=r
  selected=[]
  for r in rows.values():
   at=datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'));assert at.tzinfo
   if start<=at.astimezone(MSK)<end:selected.append({k:r.get(k)for k in FBS_FIELDS})
  assert len({r['id']for r in selected})==len(selected)and all(r['rid']and r['convertedCurrencyCode']==156 for r in selected)
  out['fbs'][str(offset)]=dict(date=str(start.date()),start_msk=start.isoformat(),end_msk=end.isoformat(),rows=selected,observed_at=stamp(),status='complete');save()
 ids=sorted({r['id']for p in out['fbs'].values()for r in p['rows']});assert len(ids)<=1000
 r=requests.post('https://marketplace-api.wildberries.ru/api/v3/orders/status',json={'orders':ids},headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(10,60));r.raise_for_status();states=r.json()['orders'];assert {r['id']for r in states}==set(ids)
 out['fbs_statuses']=dict(rows=states,observed_at=stamp());save()
 last_stats=0
 for offset in(0,1,7):
  # Respect the one-per-minute Statistics limit; no broad seven-day response.
  while last_stats and time.monotonic()-last_stats<65:
   time.sleep(min(20,65-(time.monotonic()-last_stats)))
  date=str((CUT-timedelta(days=offset)).date());last_stats=time.monotonic()
  try:
   rows=get('statistics-api.wildberries.ru','/api/v1/supplier/orders',dict(dateFrom=date,flag=1));assert isinstance(rows,list)and len(rows)<80000
   assert all(str(r['date']).startswith(date)and r.get('srid')and isinstance(r.get('isCancel'),bool)for r in rows)
   out['statistics'][str(offset)]=dict(date=date,status='complete',rows=[{k:r.get(k)for k in STATS_FIELDS}for r in rows],observed_at=stamp(),currency='not_declared_by_endpoint; compare RID money, do not assume')
  except Exception as err:out['errors']['statistics_'+str(offset)]=type(err).__name__+': '+str(err)[:180]
  save()
 out.update(status='complete'if not out['errors']else'partial',completed_at=stamp());save()
 print(json.dumps(dict(status=out['status'],source_key=ROOT,cut_msk=out['cut_msk'],fbs_counts={k:len(v['rows'])for k,v in out['fbs'].items()},statistics_counts={k:len(v['rows'])for k,v in out['statistics'].items()},errors=out['errors'],wb_writes=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':
 old=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=method=='GET'and u.path in('/api/v3/orders','/api/v3/orders/new')or method=='POST'and u.path=='/api/v3/orders/status'
  elif u.hostname=='statistics-api.wildberries.ru':ok=method=='GET'and u.path=='/api/v1/supplier/orders'and(kw.get('params')or{}).get('flag')==1
  elif u.hostname=='advert-api.wildberries.ru':ok=method=='GET'and u.path=='/adv/v1/supplier/settings'
  else:ok=False
  assert ok,'Read-only order reconciliation scope rejected'
  return old(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=old

