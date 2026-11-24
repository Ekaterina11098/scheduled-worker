import copy,json,time,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from owner_rk48024_apply import ROOT,CID,norm,REMOVE
io=AdvertisingIO();e=io.get(ROOT+':execution');assert e['wb_writes']==1 and e['ops']['exclude']['status']=='accepted'
rows=[]
for i in range(3):
 time.sleep(3);r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':CID,'owner_read':time.time_ns()},headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=50);r.raise_for_status();rows.append(r.json()['adverts'][0])
key=ROOT+':exclusion_readback';v={'status':'read','observed_at':datetime.now(timezone.utc).isoformat(),'rows':rows,'wb_writes':0,'telegram_calls':0}
io.put(key,v)if io.get(key)else io.create(key,v)
expected=copy.deepcopy(e['before']);expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']not in REMOVE]
print(json.dumps({'counts':[len(c['nm_settings'])for c in rows],'same':[norm(c)==norm(expected)for c in rows],'present':[sorted(REMOVE&{n['nm_id']for n in c['nm_settings']})for c in rows]}))
