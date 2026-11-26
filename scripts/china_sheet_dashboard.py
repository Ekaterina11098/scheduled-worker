"""Read-only spreadsheet dataset. Reuses hourly clock; no business mutations or Telegram."""
import os,json,time,uuid,zipfile,io,csv,requests
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from china_cloud_cost_control import Cache
ROOT='china_agent:sheet_dashboard:v1';MSK=ZoneInfo('Europe/Moscow')
def stamp():return datetime.now(timezone.utc).isoformat()
def run():
 c=Cache();pol=c.get(ROOT+':policy')or{};assert pol.get('enabled') and pol.get('wb_writes')==0
 clock=datetime.now(timezone.utc);day=clock.astimezone(MSK).date();slot=clock.astimezone(MSK).strftime('%Y-%m-%dT')+str(clock.astimezone(MSK).hour//2*2).zfill(2);key=ROOT+':collection:'+slot
 prior=c.get(key)
 if prior and prior.get('status')=='complete':return
 if prior and prior.get('status')in('creating','uncertain'):raise ValueError('Uncertain report generation; inspect before repeat')
 if prior is None:
  prior=dict(status='preflight',started_at=stamp(),report_id=str(uuid.uuid4()),wb_writes=0,telegram_calls=0)
  if not c.create(key,prior):return
 original=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();ok=u.hostname==urlparse(c.url).hostname and m in('GET','POST','PATCH') and u.path.startswith('/rest/v1/')
  if u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='GET' and (u.path=='/api/v2/nm-report/downloads' or u.path=='/api/v2/nm-report/downloads/file/'+prior['report_id']) or m=='POST' and u.path=='/api/v2/nm-report/downloads' and (kw.get('json')or{}).get('id')==prior['report_id']
  if u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET' and u.path=='/api/v2/list/goods/filter'
  assert ok,'Only analytics generation/read and exact price read';return original(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard;headers={'Authorization':os.environ['WB_TOKEN_3']}
 try:
  if prior['status']=='preflight':
   body=dict(id=prior['report_id'],reportType='DETAIL_HISTORY_REPORT',userReportName='VESCHI Google Sheets read-only',params=dict(nmIDs=[],subjectIds=[],brandNames=[],tagIds=[],startDate=str(max(day-timedelta(days=29),datetime(2026,11,21).date())),endDate=str(day),timezone='Europe/Moscow',aggregationLevel='day',skipDeletedNm=False));prior.update(status='creating',request=body);c.put(key,prior)
   try:r=requests.post('https://seller-analytics-api.wildberries.ru/api/v2/nm-report/downloads',headers=headers,json=body,timeout=55);r.raise_for_status();prior.update(status='requested',create_response=r.json());c.put(key,prior)
   except Exception:prior['status']='uncertain';c.put(key,prior);raise
  rawrows=None
  for attempt in range(4):
   time.sleep(21);r=requests.get('https://seller-analytics-api.wildberries.ru/api/v2/nm-report/downloads',headers=headers,params={'filter[downloadIds]':prior['report_id']},timeout=50);r.raise_for_status();prior['list']=r.json();c.put(key,prior);found=[x for x in r.json().get('data',[]) if x['id']==prior['report_id']]
   if found and found[0]['status']=='SUCCESS':
    rr=requests.get('https://seller-analytics-api.wildberries.ru/api/v2/nm-report/downloads/file/'+prior['report_id'],headers=headers,timeout=60);rr.raise_for_status();z=zipfile.ZipFile(io.BytesIO(rr.content));rawrows=[];hdr=[]
    for name in z.namelist():
     if name.endswith('.csv'):
      text=z.read(name).decode('utf-8-sig');dialect=csv.Sniffer().sniff(text[:8000],delimiters=';,\t');rd=csv.DictReader(io.StringIO(text),dialect=dialect);hdr=rd.fieldnames;rawrows.extend(list(rd))
    prior['headers']=hdr;prior['general_impressions_available']=any(x.lower()in('impressions','viewcount','showcount','impressionscount')for x in hdr);c.put(key,prior);break
  if rawrows is None:prior['status']='requested';c.put(key,prior);return
  assert rawrows and all(r['currency']=='CNY' for r in rawrows)
  r=requests.get('https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter',headers=headers,params={'limit':1000,'offset':0},timeout=55);r.raise_for_status();goods=r.json()['data']['listGoods'];assert len(goods)<1000 and all(g['currencyIsoCode4217']=='CNY' for g in goods);names={g['nmID']:g['vendorCode']for g in goods};prices={g['nmID']:g['sizes'][0]['discountedPrice'] for g in goods if len({s['discountedPrice']for s in g['sizes']})==1}
  ads={}
  # Frozen existing campaign reports contain per-day attribution; never subtract it from general traffic.
  for d in range(6):
   ds=str(day-timedelta(days=d));src=c.get('china_agent:advertising_midday_source:'+ds+':v2')or c.get('china_agent:advertising_source:'+ds+':v1')or{}
   for batch in src.get('batches',{}).values():
    for campaign in batch.get('stats',[]):
     for daily in campaign.get('days',[]):
      dt=daily['date'][:10]
      for app in daily.get('apps',[]):
       for n in app.get('nms',[]):
        k=(dt,int(n['nmId']),int(campaign['advertId']));v=ads.setdefault(k,dict(views=0,clicks=0,orders=0,spend=0,amount=0))
        for field,raw in [('views','views'),('clicks','clicks'),('orders','orders'),('spend','sum'),('amount','sum_price')]:v[field]+=n.get(raw,0)
  latest=c.get('china_agent:hourly_sales_api:v1:latest')or{};hour=c.get(latest.get('source_key',''))or{};todayads={}
  for campaign in hour.get('advertising',{}).get('stats',[]):
   for daily in campaign.get('days',[]):
    dt=daily['date'][:10]
    if dt!=str(day):continue
    for app in daily.get('apps',[]):
     for n in app.get('nms',[]):
      k=(dt,int(n['nmId']),int(campaign['advertId']));v=todayads.setdefault(k,dict(views=0,clicks=0,orders=0,spend=0,amount=0))
      for field,raw in [('views','views'),('clicks','clicks'),('orders','orders'),('spend','sum'),('amount','sum_price')]:v[field]+=n.get(raw,0)
  ads.update(todayads);adrows=[dict(date=k[0],nm=k[1],campaign=k[2],article=names.get(k[1],str(k[1])),**v)for k,v in ads.items()]
  rows=[];seen=set()
  for rr in rawrows:
   nm=int(rr['nmID']);dt=rr['dt'][:10];assert (dt,nm)not in seen;seen.add((dt,nm));order=int(rr['ordersCount']);amount=float(rr['ordersSumRub']);rows.append(dict(date=dt,nm=nm,article=names.get(nm,str(nm)),opens=int(rr['openCardCount']),carts=int(rr['addToCartCount']),orders=order,amount=amount,avg_order_price=amount/order if order else None,buyouts=int(rr['buyoutsCount']),cancels=int(rr['cancelCount']),wishlist=int(rr.get('addToWishlist') or 0),current_seller_price=prices.get(nm),asof=stamp(),partial=dt==str(day)))
  rows.sort(key=lambda x:(x['date'],x['article']));out=dict(status='complete',asof=stamp(),day=str(day),first=prior['request']['params']['startDate'],last=str(day),rows=rows,ads=adrows,catalogue=[dict(nm=g['nmID'],article=g['vendorCode'],price=prices.get(g['nmID']))for g in goods],general_impressions_available=prior['general_impressions_available'],csv_headers=prior['headers'],source_report_id=prior['report_id'],advertising_asof=hour.get('observed_at'),advertising_scope='returned campaign rows only; missing is unknown',wb_writes=0,telegram_calls=0)
  c.put(ROOT+':data',out);prior.update(status='complete',rows=len(rows),completed_at=stamp());c.put(key,prior);print(json.dumps(dict(status='complete',rows=len(rows),impressions=out['general_impressions_available'])))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':
 run()
 # Existing two-hour collector remains the only cadence; details refresh once per completed slot.
 c=Cache(); d=c.get(ROOT+':data')or{};x=c.get(ROOT+':details')or{}
 if d.get('asof') and x.get('source_dataset_asof')!=d['asof']:
  from china_sheet_details import refresh
  refresh();x=c.get(ROOT+':details');x['source_dataset_asof']=d['asof'];c.put(ROOT+':details',x)


