import os,time,json,copy,hashlib,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_blocked4_photos27:v1'
targets=json.loads("[{\"a\":\"502-AlessiaBag-cream\",\"nm\":1473244992,\"code\":\"502\",\"bytes\":165311},{\"a\":\"38-GretaBag-green\",\"nm\":1473244989,\"code\":\"38\",\"bytes\":164219},{\"a\":\"542-CelineaBag-darkbrown\",\"nm\":1473243239,\"code\":\"542\",\"bytes\":88493},{\"a\":\"539-AdaBag-coffee\",\"nm\":1473243449,\"code\":\"539\",\"bytes\":140744}]")
def now():return datetime.now(timezone.utc).isoformat()
if io.get(ROOT+':execution'):raise SystemExit('Existing journal: reconcile only, never repeat uploads')
e=dict(status='preflight',created_at=now(),items=[],wb_writes=0,telegram_calls=0);assert io.create(ROOT+':execution',e)
def save():io.put(ROOT+':execution',copy.deepcopy(e))
h={'Authorization':io.token,'Cache-Control':'no-cache'}
sh={'Authorization':'Bearer '+os.environ['SUPABASE_SECRET_KEY'],'apikey':os.environ['SUPABASE_SECRET_KEY']}
bucket='owner-media-recovery'
def card(t):
 r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers=h,json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':str(t['nm']),'withPhoto':-1}}},timeout=50);r.raise_for_status()
 rows=[x for x in r.json()['cards']if x['nmID']==t['nm']];assert len(rows)==1 and rows[0]['vendorCode']==t['a'];return rows[0]
def blocked():
 r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',headers=h,params={'sort':'nmId','order':'asc'},timeout=50);r.raise_for_status();return r.json()['report']
canon=lambda v:sorted([json.dumps(x,sort_keys=True,ensure_ascii=False)for x in v])if isinstance(v,list)else v
keys=('vendorCode','description','characteristics','sizes','dimensions','title','brand','video')
try:
 blocks=blocked();transfers=[]
 for t in targets:
  c=card(t);assert not c.get('photos'),'Existing photos: preserve'
  item=dict(target=t,before=c,blocked_before=[x for x in blocks if x['nmId']==t['nm']],status='preflight');e['items'].append(item);save()
  obj='blocked4-27/'+t['code']+'.jpg'
  r=requests.post(io.url+'/storage/v1/object/upload/sign/'+bucket+'/'+obj,headers=sh,json={'upsert':False},timeout=40);r.raise_for_status()
  signed=r.json()['url'];signed=io.url+'/storage/v1'+signed if signed.startswith('/object/')else(io.url+signed if signed.startswith('/')else signed)
  transfers.append(dict(code=t['code'],upload_url=signed))
 io.create(ROOT+':transfer',dict(items=transfers,created_at=now()))
 e['status']='awaiting_source';save()
 for item in e['items']:
  t=item['target'];obj='blocked4-27/'+t['code']+'.jpg'
  for _ in range(84):
   r=requests.get(io.url+'/storage/v1/object/authenticated/'+bucket+'/'+obj,headers=sh,timeout=40)
   if r.ok:break
   assert r.status_code in(400,404)
   time.sleep(5)
  else:raise ValueError('Photo transfer missing:'+t['code'])
  raw=r.content;assert len(raw)==t['bytes']and raw[:2]==b'\xff\xd8'
  item['source_sha256']=hashlib.sha256(raw).hexdigest()
  check=card(t);assert not check.get('photos')and all(canon(check.get(k))==canon(item['before'].get(k))for k in keys),'Content changed'
  item['operation']=dict(status='submitting',at=now(),slot=1);save()
  r=requests.post('https://content-api.wildberries.ru/content/v3/media/file',headers={**h,'X-Nm-Id':str(t['nm']),'X-Photo-Number':'1'},files={'uploadfile':(t['code']+'.jpg',raw,'image/jpeg')},timeout=90)
  item['operation'].update(status='accepted'if r.ok else'rejected',http_status=r.status_code,response=r.text[:1500]);save();r.raise_for_status();assert not r.json().get('error')
  e['wb_writes']+=1;save()
  for _ in range(12):
   time.sleep(5);after=card(t);item['after']=after;save()
   if len(after.get('photos')or[])==1:break
  assert len(after.get('photos')or[])==1,'Photo not visible:'+t['code']
  assert all(canon(after.get(k))==canon(item['before'].get(k))for k in keys),'Unrelated content changed'
  item.update(status='photo_verified',verified_at=now());save()
 blocks=blocked()
 for item in e['items']:item['blocked_after']=[x for x in blocks if x['nmId']==item['target']['nm']]
 e.update(status='verified',verified_at=now());save()
except Exception as ex:
 e.update(status='needs_reconciliation'if any(x.get('operation')for x in e['items'])else'blocked',error=type(ex).__name__+':'+str(ex)[:400]);save()
print(json.dumps({'status':e['status'],'error':e.get('error'),'wb_writes':e['wb_writes']}))
