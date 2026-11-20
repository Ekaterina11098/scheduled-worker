"""One read-only current budget and traffic check for an exact private campaign."""
import requests,json
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_advertising_v2 import http
ROOT='china_agent:fur_search_budget:2026-11-20:v1'
def main():
 io=AdvertisingIO();spec=io.get('china_agent:fur_search_review:2026-11-20:v1:request');cid=spec['campaign_id']
 out=dict(status='collecting',wb_writes=0,telegram_calls=0,model_calls=0,errors={});assert io.create(ROOT,out)
 def save():io.put(ROOT,out)
 for name,path,method,body in [('campaign','/api/advert/v2/adverts?ids='+str(cid),'GET',None),('budget','/api/advert/v2/budget','POST',dict(advertIds=[cid])),('stats','/adv/v3/fullstats?ids='+str(cid)+'&beginDate=2026-11-20&endDate=2026-11-20','GET',None)]:
  try:out[name]=dict(response=http(io,path,method,body),observed_at=datetime.now(timezone.utc).isoformat())
  except Exception as ex:out['errors'][name]=str(ex)[:200]
  save()
 out['status']='complete'if not out['errors']else'partial';save();print(json.dumps(dict(status=out['status'],errors=out['errors'])))
if __name__=='__main__':main()
