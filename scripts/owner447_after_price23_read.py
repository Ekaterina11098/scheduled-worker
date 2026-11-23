import json,time,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner447_after_price:2026-11-23:v1'
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v['status']=='complete':print('Already read');return
 if not v:v=dict(status='reading',wb_writes=0,telegram_calls=0,model_calls=0,errors={},observed_at=datetime.now(timezone.utc).isoformat());assert io.create(ROOT,v)
 for key,start,end,pstart,pend in [('change_day','2026-11-22','2026-11-22','2026-11-19','2026-11-21'),('today','2026-11-23','2026-11-23','2026-11-22','2026-11-22')]:
  if key in v:continue
  if key=='today':time.sleep(21)
  try:
   body=dict(selectedPeriod={'start':start,'end':end},pastPeriod={'start':pstart,'end':pend},nmIds=[1473244340],brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
   r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},json=body,timeout=(10,60));r.raise_for_status();v[key]=dict(observed_at=datetime.now(timezone.utc).isoformat(),request=body,response=r.json());v['errors'].pop(key,None)
  except Exception as ex:v['errors'][key]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT,v)
 v['status']='complete'if not v['errors']else'complete_with_gaps';v['completed_at']=datetime.now(timezone.utc).isoformat();io.put(ROOT,v);print(json.dumps({'status':v['status'],'errors':v['errors']}))
if __name__=='__main__':main()
