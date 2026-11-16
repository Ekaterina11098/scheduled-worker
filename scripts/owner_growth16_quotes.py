"""Two exact existing-member bid minima; read-only, no repeat of economic reads."""
import os,json,requests,time
from china_cloud_cost_control import Cache,stamp
KEY='china_agent:owner_growth046_58_643:2026-11-16:v1:exact_quotes'
c=Cache()
if not c.create(KEY+':claim',dict(at=stamp())):raise RuntimeError('Already claimed')
out=dict(observed_at=stamp(),wb_writes=0,model_calls=0,telegram_calls=0,quotes={},errors={})
for cid,nm,placement in [(40933588,1473243896,'recommendation'),(41298169,1473243910,'search')]:
 r=requests.post('https://advert-api.wildberries.ru/api/advert/v1/bids/min',headers={'Authorization':os.environ['WB_TOKEN_3']},json=dict(advert_id=cid,nm_ids=[nm],payment_type='cpc',placement_types=[placement]),timeout=45)
 if r.ok:out['quotes'][str(cid)]=r.json()
 else:out['errors'][str(cid)]=dict(http=r.status_code,body=r.text[:800])
 time.sleep(2)
out['status']='complete'if not out['errors']else'partial'
c.put(KEY,out);print(json.dumps(dict(status=out['status'])))
