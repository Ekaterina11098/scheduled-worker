import requests,json,time,os
from datetime import datetime,timezone,timedelta
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_order6320310775_route27:v1';h={'Authorization':io.token}
def save(k,p):
 if io.get(k) is None:io.create(k,p)
 else:io.put(k,p)
def get(path,params=None):
 r=requests.get('https://marketplace-api.wildberries.ru'+path,headers=h,params=params,timeout=60);return dict(status=r.status_code,data=r.json()if r.ok else r.text[:300])
if not io.get(ROOT+':order'):
 n=0
 for _ in range(5):
  j=get('/api/v3/orders',dict(limit=1000,next=n,dateFrom=1795305600,dateTo=1795478400))
  if j['status']!=200:save(ROOT+':order',j);break
  p=j['data'];found=[x for x in p.get('orders',[])if x.get('id')==6320310775]
  if found:save(ROOT+':order',dict(status=200,orders=found));break
  n2=p.get('next')
  if not n2 or n2==n:save(ROOT+':order',dict(status=200,orders=[],complete=True));break
  n=n2;time.sleep(.5)
if not io.get(ROOT+':supply'):
 n=0;found=False;candidates=[]
 for _ in range(5):
  j=get('/api/v3/supplies',dict(limit=1000,next=n))
  if j['status']!=200:save(ROOT+':supply',j);break
  p=j['data'];candidates += [x for x in p.get('supplies',[])if '2026-11-21'<=str(x.get('createdAt',''))[:10]<='2026-11-26']
  n2=p.get('next')
  if not n2 or n2==n:break
  n=n2;time.sleep(.5)
 save(ROOT+':candidates',dict(supplies=candidates))
 for x in candidates:
  k=ROOT+':ids:'+x['id'];j=io.get(k)
  if not j:j=get('/api/marketplace/v3/supplies/'+x['id']+'/order-ids');save(k,j)
  if j['status']==200 and 6320310775 in j['data'].get('orderIds',[]):
   save(ROOT+':supply',dict(supply=x,details=get('/api/v3/supplies/'+x['id'])));found=True;break
  time.sleep(.4)
 if not found:save(ROOT+':supply',dict(status='not_found',candidates_checked=len(candidates)))
if not io.get(ROOT+':finance_row'):
 rate=io.get('china_agent:wb_evidence:v1:rate:finance')or{}
 retry=rate.get('retry_at');clock=datetime.now(timezone.utc)
 wait=(datetime.fromisoformat(retry)-clock).total_seconds()if retry else 0
 if 0<wait<120:time.sleep(wait+1)
 if wait<120:
  clock=datetime.now(timezone.utc);claim='china_agent:wb_evidence:v1:rate_claim:finance:'+str(int(clock.timestamp())//61)
  if io.create(claim,dict(started_at=clock.isoformat())):
   save('china_agent:wb_evidence:v1:rate:finance',dict(retry_at=(clock+timedelta(seconds=61)).isoformat()))
   r=requests.post('https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed',headers=h,json=dict(dateFrom='2026-11-26',dateTo='2026-11-26',period='daily',rrdId=1602200788,limit=1000),timeout=90)
   save(ROOT+':finance_row',dict(status=r.status_code,rows=[x for x in r.json()if str(x.get('orderId'))=='6320310775']if r.status_code==200 else []))
print('Read-only route lookup saved')
