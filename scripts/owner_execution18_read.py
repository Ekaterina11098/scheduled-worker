import json,requests,time
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_package_readback import check
from china_daily_ad_actions import execution_order
KEY='china_agent:owner_execution18_reconcile:v1:read'
PLAN='daily-2026-11-18-owner-review18-r3-drr-0-buttons-d320db1e7225965af79b9278-5122667182'
io=AdvertisingIO();assert not io.get(KEY)
p=io.get('china_agent:loss_plan:v1:'+PLAN);e=io.get('china_agent:daily_ad_execution:v2:'+PLAN)
ids=[40933588,40945478,41270309];rounds=[]
for n in range(2):
 if n:time.sleep(4)
 r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',params={'ids':','.join(map(str,ids))},headers={'Authorization':io.token},timeout=50);r.raise_for_status()
 states={c['id']:c for c in r.json()['adverts']};assert set(states)==set(ids)
 bad,groups=check(execution_order(p['items']),e['items'],states)
 rounds.append(dict(observed_at=datetime.now(timezone.utc).isoformat(),campaigns={str(k):v for k,v in states.items()},errors=bad))
r=requests.post('https://advert-api.wildberries.ru/api/advert/v2/budget',json=dict(advertIds=[40933588,41779660]),headers={'Authorization':io.token},timeout=50);r.raise_for_status()
assert io.create(KEY,dict(status='read_complete',rounds=rounds,budgets=r.json(),wb_writes=0,model_calls=0,telegram_calls=0))
print(json.dumps(dict(status='read_complete',errors=[r['errors']for r in rounds],wb_writes=0)))

