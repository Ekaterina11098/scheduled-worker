"""Exact existing-member minimum quotes only, no WB mutations."""
import json,time,requests
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_seven_recovery25:v1:minima_existing'
def main():
 io=AdvertisingIO()
 if io.get(ROOT):print('Existing checkpoint retained');return
 out=dict(status='reading',quotes={},errors={},wb_writes=0,telegram_calls=0,observed_at=datetime.now(timezone.utc).isoformat());assert io.create(ROOT,out)
 def save():io.put(ROOT,out)
 for cid,zone,ids in [(40933588,'recommendation',[1473244345,1473243914]),(41055480,'recommendation',[1473244360]),(41270309,'recommendation',[1473244341]),(42068228,'search',[1473246040])]:
  time.sleep(2)
  r=requests.post('https://advert-api.wildberries.ru/api/advert/v1/bids/min',headers={'Authorization':io.token},json=dict(advert_id=cid,nm_ids=ids,payment_type='cpc',placement_types=[zone]),timeout=45)
  if r.ok:out['quotes'][str(cid)]=r.json()
  else:out['errors'][str(cid)]=dict(http=r.status_code,body=r.text[:300])
  save()
 out['status']='complete'if not out['errors']else'partial';save();print(json.dumps(dict(status=out['status'],errors=out['errors'])))
if __name__=='__main__':main()
