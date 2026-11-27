import os,time,json,copy,hashlib,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_674_photo27:v1';NM=1473243829
def now():return datetime.now(timezone.utc).isoformat()
e=io.get(ROOT+':execution')
if e:raise SystemExit('Existing journal; no replay')
e=dict(status='preflight',created_at=now(),wb_writes=0,telegram_calls=0)
assert io.create(ROOT+':execution',e)
def save():io.put(ROOT+':execution',copy.deepcopy(e))
h={'Authorization':io.token,'Cache-Control':'no-cache'}
def card():
 r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers=h,json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':str(NM),'withPhoto':-1}}},timeout=50);r.raise_for_status()
 rows=[x for x in r.json()['cards']if x['nmID']==NM];assert len(rows)==1 and rows[0]['vendorCode']=='674-NoelBag-pink';return rows[0]
def blocked():
 r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',headers=h,params={'sort':'nmId','order':'asc'},timeout=50);r.raise_for_status();return [x for x in r.json()['report']if x['nmId']==NM]
try:
 e['before']=card();e['blocked_before']=blocked();save()
 assert not e['before'].get('photos'),'Existing photos; preserve and reconcile'
 sh={'Authorization':'Bearer '+os.environ['SUPABASE_SECRET_KEY'],'apikey':os.environ['SUPABASE_SECRET_KEY']}
 obj='674-photo27/source.png';bucket='owner-media-recovery'
 r=requests.post(io.url+'/storage/v1/object/upload/sign/'+bucket+'/'+obj,headers=sh,json={'upsert':False},timeout=40);r.raise_for_status()
 signed=r.json()['url'];signed=io.url+signed if signed.startswith('/')else signed
 io.create(ROOT+':transfer',{'upload_url':signed,'created_at':now()})
 e['status']='awaiting_source';save()
 for i in range(84):
  r=requests.get(io.url+'/storage/v1/object/authenticated/'+bucket+'/'+obj,headers=sh,timeout=40)
  if r.ok:break
  assert r.status_code in(400,404),str(r.status_code)
  time.sleep(5)
 else:raise ValueError('Source transfer pending; no WB upload')
 raw=r.content
 assert raw[:8]==b'\x89PNG\r\n\x1a\n'and len(raw)==6426149
 e['source_sha256']=hashlib.sha256(raw).hexdigest()
 assert card()==e['before'],'Card changed before upload'
 e['operation']={'status':'submitting','at':now(),'slot':1};save()
 r=requests.post('https://content-api.wildberries.ru/content/v3/media/file',headers={**h,'X-Nm-Id':str(NM),'X-Photo-Number':'1'},files={'uploadfile':('674-pink.png',raw,'image/png')},timeout=90)
 e['operation'].update(http_status=r.status_code,response=r.text[:2000],status='accepted'if r.ok else'rejected');save();r.raise_for_status()
 assert not r.json().get('error')
 e['wb_writes']=1;save()
 for i in range(12):
  time.sleep(5);e['after']=card();save()
  if len(e['after'].get('photos')or[])==1:break
 assert len(e['after'].get('photos')or[])==1,'Photo not yet visible'
 for k in('vendorCode','description','characteristics','sizes','dimensions','title','brand','video'):assert e['after'].get(k)==e['before'].get(k),'Unrelated content changed'
 e['blocked_after']=blocked();e.update(status='verified',verified_at=now());save()
except Exception as ex:
 e.update(status='needs_reconciliation'if e.get('operation')else'blocked',error=type(ex).__name__+':'+str(ex)[:450]);save()
print(json.dumps({'status':e['status'],'error':e.get('error'),'wb_writes':e['wb_writes']}))
