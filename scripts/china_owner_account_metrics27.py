import requests,time,json
from datetime import datetime,timezone,timedelta
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_account_metrics27:v1:1646'
h={'Authorization':io.token,'Cache-Control':'no-cache'}
def stamp():return datetime.now(timezone.utc).isoformat()
def save(s,p):
 k=ROOT+':'+s
 if not io.get(k):io.create(k,p)
 else:io.put(k,p)
d=datetime.now(timezone(timedelta(hours=3))).date();start=datetime.combine(d,datetime.min.time(),tzinfo=timezone(timedelta(hours=3)));clock=datetime.now(timezone.utc)
if not io.get(ROOT+':orders'):
 rows=[];n=0;status=None;complete=False
 for _ in range(5):
  r=requests.get('https://marketplace-api.wildberries.ru/api/v3/orders',headers=h,params=dict(limit=1000,next=n,dateFrom=int(start.timestamp()),dateTo=int(clock.timestamp())),timeout=60);status=r.status_code
  if not r.ok:break
  j=r.json();p=j.get('orders',[]);rows+=p;nn=j.get('next')
  if not p or not nn or nn==n:complete=True;break
  n=nn;time.sleep(.5)
 fields=['id','createdAt','article','nmId','convertedPrice','convertedCurrencyCode','isZeroOrder']
 save('orders',dict(status=status,complete=complete,rows=[{k:x.get(k)for k in fields}for x in rows],observed_at=stamp()))
if not io.get(ROOT+':ads'):
 source=io.get('china_agent:advertising_full_growth:2026-11-27:v1:inputs:midday')
 ids=sorted(c['id']for c in source['campaigns'])
 r=requests.get('https://advert-api.wildberries.ru/adv/v3/fullstats',headers=h,params=dict(ids=','.join(map(str,ids)),beginDate=str(d),endDate=str(d)),timeout=90)
 save('ads',dict(status=r.status_code,requested_ids=ids,data=r.json()if r.ok else None,observed_at=stamp()))
if not io.get(ROOT+':funnel'):
 rate=io.get('china_agent:wb_evidence:v1:rate:funnel')or{}
 retry=rate.get('retry_at');wait=(datetime.fromisoformat(retry)-datetime.now(timezone.utc)).total_seconds()if retry else 0
 if wait>120:save('funnel',dict(status='cooldown',retry_at=retry))
 else:
  if wait>0:time.sleep(wait+1)
  body=dict(selectedPeriod={'start':str(d),'end':str(d)},pastPeriod={'start':str(d-timedelta(days=1)),'end':str(d-timedelta(days=1))},nmIds=[],brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=1000,offset=0)
  r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers=h,json=body,timeout=90)
  save('funnel',dict(status=r.status_code,data=r.json()if r.ok else None,observed_at=stamp(),request=body))
print('Whole cabinet read only metrics saved')
