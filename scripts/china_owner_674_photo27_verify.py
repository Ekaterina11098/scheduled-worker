import json,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();ROOT='china_agent:owner_674_photo27:v1';e=io.get(ROOT+':execution')
assert e['wb_writes']==1 and e['operation']['status']=='accepted'
h={'Authorization':io.token,'Cache-Control':'no-cache'}
r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers=h,json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':'1473243829','withPhoto':-1}}},timeout=50);r.raise_for_status()
c=next(x for x in r.json()['cards']if x['nmID']==1473243829)
canon=lambda v:sorted([json.dumps(x,sort_keys=True,ensure_ascii=False)for x in v])if isinstance(v,list)else v
assert len(c.get('photos')or[])==1
assert all(canon(c.get(k))==canon(e['before'].get(k))for k in('vendorCode','description','characteristics','sizes','dimensions','title','brand','video'))
r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',headers=h,params={'sort':'nmId','order':'asc'},timeout=50);r.raise_for_status()
e.update(after=c,blocked_after=[x for x in r.json()['report']if x['nmId']==1473243829],status='verified',verified_at=datetime.now(timezone.utc).isoformat(),reconciliation='Characteristics order differs only; exact values preserved, no upload replay')
e.pop('error',None);io.put(ROOT+':execution',e)
print(json.dumps({'status':e['status'],'photos':len(c['photos']),'still_blocked':bool(e['blocked_after'])}))
