import requests,json
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
io=AdvertisingIO();root='china_agent:owner_offices_kirov27:v1'
if io.get(root):raise SystemExit('Saved read exists')
out={'status':'reading','observed_at':datetime.now(timezone.utc).isoformat(),'wb_writes':0,'telegram_calls':0}
for name,path in [('offices','/api/v3/offices'),('warehouses','/api/v3/warehouses')]:
 r=requests.get('https://marketplace-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},timeout=50);r.raise_for_status();out[name]=r.json()
out['status']='complete';out['completed_at']=datetime.now(timezone.utc).isoformat();assert io.create(root,out)
print(json.dumps({'status':out['status'],'offices':len(out['offices'])}))
