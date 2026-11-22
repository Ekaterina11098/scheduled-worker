"""Owner-requested bounded read-only current campaign/budget verification."""
import json
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
ROOT='china_agent:owner_sales_recovery:2026-11-22:v1:current'
IDS=[40933588,40945478,40945502,40964981,41055480,41155909,41187173,41270309,41298169,41325622,41332083,41680341,41680449,41779660,41967612,42022679,42068146,42068186,42068228,42068265,42088552]
def main():
 io=AdvertisingIO()
 if io.get(ROOT):print('Existing checkpoint; no replay');return
 now=lambda:datetime.now(timezone.utc).isoformat()
 out=dict(status='reading',observed_at=now(),wb_writes=0,telegram_calls=0,model_calls=0)
 out['campaigns']=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,IDS)))
 out['budgets']=http(io,'/api/advert/v2/budget','POST',dict(advertIds=IDS))
 out.update(status='complete',completed_at=now());io.create(ROOT,out)
 print(json.dumps(dict(status=out['status'],campaign_count=len(out['campaigns'].get('adverts',[])))))
if __name__=='__main__':main()
