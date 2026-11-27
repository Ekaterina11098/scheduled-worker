import requests,json
from datetime import datetime,timezone,timedelta
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();k='china_agent:owner_latestorders27:v1:check1525'
if io.get(k):raise SystemExit('Already saved')
start=datetime.now(timezone.utc);today=start.astimezone(timezone(timedelta(hours=3))).replace(hour=0,minute=0,second=0,microsecond=0)
h={'Authorization':io.token,'Cache-Control':'no-cache'}
out=dict(started_at=start.isoformat(),wb_writes=0,telegram_sends=0)
r=requests.get('https://marketplace-api.wildberries.ru/api/v3/orders/new',headers=h,timeout=60)
out['new_status']=r.status_code
if r.ok:
 rows=r.json().get('orders',[]);out['new_count']=len(rows);out['new_latest']=[{k:x.get(k)for k in ['id','createdAt','article','warehouseId','officeId','price','convertedPrice','currencyCode','convertedCurrencyCode']}for x in sorted(rows,key=lambda x:x.get('createdAt',''),reverse=True)[:15]]
n=0;allrows=[]
for _ in range(5):
 r=requests.get('https://marketplace-api.wildberries.ru/api/v3/orders',headers=h,params=dict(limit=1000,next=n,dateFrom=int(today.timestamp()),dateTo=int(start.timestamp())),timeout=60)
 out['history_status']=r.status_code
 if not r.ok:break
 p=r.json();rows=p.get('orders',[]);allrows+=rows;n2=p.get('next')
 if not rows or not n2 or n2==n:out['history_complete']=True;break
 n=n2
out['today_history_count']=len(allrows)
out['history_latest']=[{k:x.get(k)for k in ['id','createdAt','article','warehouseId','officeId']}for x in sorted(allrows,key=lambda x:x.get('createdAt',''),reverse=True)[:15]]
out['finished_at']=datetime.now(timezone.utc).isoformat()
io.create(k,out);print('Readonly latest order check saved')
