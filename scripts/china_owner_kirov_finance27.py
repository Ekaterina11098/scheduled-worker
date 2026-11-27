import requests,json,time,base64,os
from datetime import datetime,timezone,timedelta
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_kirov_supplyfees27:v1'
def save(k,p):
 if io.get(k) is None:io.create(k,p)
 else:io.put(k,p)
h={'Authorization':io.token}
sup=io.get(ROOT+':supplies')['matches']
for x in sup:
 k=ROOT+':orderids:'+x['id']
 if io.get(k):continue
 r=requests.get('https://marketplace-api.wildberries.ru/api/marketplace/v3/supplies/'+x['id']+'/order-ids',headers=h,timeout=60)
 save(k,dict(status=r.status_code,data=r.json()if r.ok else r.text[:300],observed_at=datetime.now(timezone.utc).isoformat()))
 time.sleep(1)
# Read history once for exact supply order linkage.
k=ROOT+':orderhistory'
if not io.get(k):
 rows=[];n=0
 for _ in range(20):
  r=requests.get('https://marketplace-api.wildberries.ru/api/v3/orders',headers=h,params=dict(limit=1000,next=n,dateFrom=int(datetime(2026,10,18,tzinfo=timezone.utc).timestamp()),dateTo=int(datetime(2026,11,5,tzinfo=timezone.utc).timestamp())),timeout=60)
  if not r.ok:save(k,dict(status=r.status_code,orders=rows));break
  j=r.json();p=j.get('orders',[]);rows+=p
  if not p or not j.get('next') or j['next']==n:save(k,dict(status=200,complete=True,orders=rows));break
  n=j['next'];time.sleep(1)
# Collect published finance, preserving checkpoints and global rate gate.
token=os.environ.get('WB_FINANCE_TOKEN_3')or io.token
try:acc=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'===' )).get('acc')
except Exception:acc=None
interval=43201 if acc==1 else 61
for first,last in [('2026-10-21','2026-11-20'),('2026-11-21','2026-11-27')]:
 k=ROOT+':finance:'+first+':'+last;s=io.get(k)or dict(rows=[],rrd_id=0,complete=False)
 for _ in range(5):
  if s.get('complete'):break
  rate=io.get('china_agent:wb_evidence:v1:rate:finance')or{}
  retry=rate.get('retry_at')
  wait=(datetime.fromisoformat(retry)-datetime.now(timezone.utc)).total_seconds() if retry else 0
  if wait>300:save(k,dict(s,status='cooldown',retry_at=retry));break
  if wait>0:time.sleep(wait+1)
  clock=datetime.now(timezone.utc)
  claim='china_agent:wb_evidence:v1:rate_claim:finance:'+str(int(clock.timestamp())//interval)
  if not io.create(claim,dict(started_at=clock.isoformat())):time.sleep(62);continue
  save('china_agent:wb_evidence:v1:rate:finance',dict(retry_at=(clock+timedelta(seconds=interval)).isoformat()))
  r=requests.post('https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed',headers={'Authorization':token},json=dict(dateFrom=first,dateTo=last,period='daily',limit=100000,rrdId=s['rrd_id']),timeout=100)
  if r.status_code==204:s['complete']=True
  elif r.status_code==200:
   p=r.json()
   if not isinstance(p,list):save(k,dict(s,status='unexpected_shape'));break
   ids={str(v) for x in sup for v in (io.get(ROOT+':orderids:'+x['id'])or{}).get('data',{}).get('orderIds',[])}
   fields=['rrdId','reportId','orderId','orderUid','srid','stickerId','nmId','vendorCode','rrDate','saleDt','orderDt','sellerOperName','bonusTypeName','currency','penalty','deduction','additionalPayment','rebillLogisticCost','paidAcceptance','paidStorage','deliveryService','commissionPercent','kvw','kvwBase','supRatingUp','dlvPrc','warehouseLogisticsCoeff','giId']
   fees=['penalty','deduction','additionalPayment','rebillLogisticCost','paidAcceptance']
   kept=[{k:v for k,v in row.items()if k in fields}for row in p if str(row.get('orderId'))in ids or any(float(row.get(k)or 0)!=0 for k in fees)]
   s['rows']+=kept;s['scanned_rows']=s.get('scanned_rows',0)+len(p)
   if p:s['rrd_id']=p[-1]['rrdId']
   else:save(k,dict(s,status='empty200'));break
  else:save(k,dict(s,status=r.status_code));break
  s.update(status='ok',observed_at=clock.isoformat());save(k,s)
print('Read-only Kirov linkage and finance saved')
