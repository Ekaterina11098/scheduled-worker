import json,time,requests,copy
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from owner_return45_apply import norm
ROOT='china_agent:owner_return45_apply:2026-11-22:v2'
def main():
 io=AdvertisingIO();e=io.get(ROOT+':execution');out=dict(status='reading',observed_at=datetime.now(timezone.utc).isoformat(),batches=[],wb_writes=0)
 if io.get(ROOT+':reconcile'):io.put(ROOT+':reconcile',out)
 else:assert io.create(ROOT+':reconcile',out)
 ids=[g['cid']for g in e['groups']]+[42088552]
 for _ in range(3):
  time.sleep(3);r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':','.join(map(str,ids)),'owner_read':time.time_ns()},headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();out['batches'].append(r.json()['adverts']);io.put(ROOT+':reconcile',out)
 out['status']='complete';out['completed_at']=datetime.now(timezone.utc).isoformat();io.put(ROOT+':reconcile',out)
 print(json.dumps(dict(status='complete',counts={c['id']:len(c['nm_settings'])for c in out['batches'][-1]})))
if __name__=='__main__':main()

