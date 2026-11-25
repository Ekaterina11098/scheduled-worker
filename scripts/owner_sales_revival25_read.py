"""Read-only full-cabinet price-rise diagnosis; checkpoints prevent repeated report creation."""
import os,json,time,uuid,zipfile,io,csv,base64,hashlib,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import validate_identity
ROOT='china_agent:owner_sales_revival:2026-11-25:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 db=AdvertisingIO();state=db.get(ROOT)or dict(status='collecting',started_at=stamp(),errors={},wb_writes=0,telegram_calls=0,model_calls=0)
 if state.get('status')=='complete':print('Saved complete diagnosis inputs; no repeated API calls');return
 if db.get(ROOT)is None:assert db.create(ROOT,state)
 def save():db.put(ROOT,state)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  ok=u.hostname==urlparse(db.url).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  if u.hostname=='seller-analytics-api.wildberries.ru':ok=(m=='POST'and u.path in('/api/analytics/v3/sales-funnel/products','/api/v2/nm-report/downloads','/api/v2/search-report/table/details'))or(m=='GET'and(u.path=='/api/v2/nm-report/downloads'or u.path.startswith('/api/v2/nm-report/downloads/file/')))
  if not ok:raise ValueError('Diagnosis forbids marketplace mutations, Telegram, models or unrelated network')
  return orig(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 cat=db.get('china_agent:prices:v1');assert cat['cabinet']=='token_3'and all(r['currencyIsoCode4217']=='CNY'for r in cat['rows'])
 ids=sorted(r['nmID']for r in cat['rows']);state.setdefault('catalogue_reference',dict(source_key='china_agent:prices:v1',observed_at=cat['observed_at'],nm_ids=ids))
 if 'funnel_today'not in state:
  from china_wb_evidence import Reports
  class Adapter:
   def get(self,k):return db.get(k)
   def save(self,k,v):return db.put(k,v)if db.get(k)is not None else db.create(k,v)
   def db(self,method,table,params=None,body=None,prefer=None):
    assert table=='telegram_api_cache'
    from urllib.parse import urlencode
    return db.db(table+'?'+urlencode(params or{}),method,body,prefer)
  result=Reports(Adapter()).funnel('2026-11-25','2026-11-25')
  if result.get('complete'):state['funnel_today']=result
  else:state['errors']['funnel_today']=dict(status=result.get('status'),retry_at=result.get('retry_at'))
  save()
 # Exactly one broad daily export. Creating an analytics file does not change business data.
 export=state.get('daily_export')
 host='https://seller-analytics-api.wildberries.ru';headers={'Authorization':db.token}
 if export is None:
  rid=str(uuid.uuid4());body=dict(id=rid,reportType='DETAIL_HISTORY_REPORT',userReportName='Owner price rise diagnosis 21-25Nov',params=dict(nmIDs=ids,tagIds=[],brandNames=[],subjectIds=[],startDate='2026-11-21',endDate='2026-11-25',timezone='Europe/Moscow',skipDeletedNm=False,aggregationLevel='day'))
  export=dict(status='creating',report_id=rid,request=body,created_at=stamp());state['daily_export']=export;save()
  try:
   r=requests.post(host+'/api/v2/nm-report/downloads',headers=headers,json=body,timeout=(10,60))
   export['create_http']=r.status_code
   if r.status_code!=200:export['status']='create_unavailable'
   else:export['status']='created'
   save()
  except Exception:export['status']='create_uncertain';save();raise
 if export['status']in('creating','create_uncertain'):raise ValueError('Report creation uncertain; no duplicate creation')
 if export['status']=='created':
  for attempt in range(8):
   if attempt:time.sleep(30)
   r=requests.get(host+'/api/v2/nm-report/downloads',headers=headers,params={'filter[downloadIds]':export['report_id']},timeout=(10,50))
   export['poll_http']=r.status_code
   if r.status_code!=200:save();break
   report=next((x for x in r.json().get('data',[])if x.get('id')==export['report_id']),{})
   export['report_state']=report;save()
   if report.get('status')=='FAILED':export['status']='generation_failed';save();break
   if report.get('status')!='SUCCESS':continue
   r=requests.get(host+'/api/v2/nm-report/downloads/file/'+export['report_id'],headers=headers,timeout=(10,90));export['download_http']=r.status_code
   if r.status_code!=200:save();break
   raw=r.content;assert zipfile.is_zipfile(io.BytesIO(raw));tables=[]
   with zipfile.ZipFile(io.BytesIO(raw))as z:
    assert z.testzip()is None
    for name in z.namelist():
     if not name.endswith('.csv'):continue
     text=z.read(name).decode('utf-8-sig');dialect=csv.Sniffer().sniff(text[:12000],delimiters=';,\t')
     reader=csv.DictReader(io.StringIO(text),dialect=dialect);rows=list(reader)
     assert {'nmID','dt','openCardCount','addToCartCount','ordersCount','currency'}<=set(reader.fieldnames)
     assert all(x['currency']=='CNY'and int(x['nmID'])in ids for x in rows)
     tables.append(dict(name=name,headers=reader.fieldnames,rows=rows))
   assert tables
   archive=dict(data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest(),observed_at=stamp(),report_id=export['report_id'])
   assert db.create(ROOT+':archive',archive)
   export.update(status='complete',observed_at=stamp(),tables=tables,archive_sha256=archive['sha256']);save();break
 if 'search_probe'not in state:
  body=dict(currentPeriod=dict(start='2026-11-25',end='2026-11-25'),pastPeriod=dict(start='2026-11-24',end='2026-11-24'),orderBy=dict(field='avgPosition',mode='asc'),positionCluster='all',includeSubstitutedSKUs=True,includeSearchTexts=False,limit=1000,offset=0)
  r=requests.post(host+'/api/v2/search-report/table/details',headers=headers,json=body,timeout=(10,60))
  state['search_probe']=dict(observed_at=stamp(),http=r.status_code,request=body)
  if r.status_code==200:state['search_probe']['response']=r.json()
  else:
   try:j=r.json();state['search_probe']['error']={k:j[k]for k in('title','detail','message')if k in j}
   except Exception:pass
  save()
 state.update(status='complete'if export['status']=='complete'and'funnel_today'in state else'partial',completed_at=stamp());save()
 print(json.dumps(dict(status=state['status'],daily_export=export['status'],search_http=state['search_probe']['http'],wb_writes=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':main()

