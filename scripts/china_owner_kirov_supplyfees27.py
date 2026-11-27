import requests,json,time
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_kirov_supplyfees27:v1'
out=io.get(ROOT+':supplies')or dict(status='reading',pages=[],matches=[],next=0,wb_writes=0,telegram_calls=0)
if out['status']=='complete':raise SystemExit('Saved discovery')
if not io.get(ROOT+':supplies'):assert io.create(ROOT+':supplies',out)
h={'Authorization':io.token,'Cache-Control':'no-cache'}
for _ in range(30):
 r=requests.get('https://marketplace-api.wildberries.ru/api/v3/supplies',headers=h,params={'limit':1000,'next':out['next']},timeout=50);r.raise_for_status();j=r.json();rows=j['supplies']
 out['pages'].append({'count':len(rows),'next':out['next'],'range':{'first':rows[0]if rows else None,'last':rows[-1]if rows else None}})
 out['matches'] += [x for x in rows if 'киров'in (x.get('name')or'').lower()or'kirov'in(x.get('name')or'').lower()]
 n=j.get('next');out['next']=n;out['observed_at']=datetime.now(timezone.utc).isoformat();io.put(ROOT+':supplies',out)
 if not rows or not n or n==out['pages'][-1]['next']:out['status']='complete';break
 time.sleep(.8)
if out['status']!='complete':out['status']='partial'
io.put(ROOT+':supplies',out)
for x in out['matches']:
 key=ROOT+':orders:'+x['id']
 if io.get(key):continue
 r=requests.get('https://marketplace-api.wildberries.ru/api/v3/supplies/'+x['id']+'/orders',headers=h,timeout=50)
 io.create(key,{'supply':x,'http_status':r.status_code,'data':r.json()if r.ok else r.text[:500],'observed_at':datetime.now(timezone.utc).isoformat()})
print(json.dumps({'status':out['status'],'matches':out['matches'],'pages':len(out['pages'])},ensure_ascii=False))
