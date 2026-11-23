import json,time,requests,copy
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_raise_review:2026-11-23:v1'
ITEMS=[(1473243890,'595-Noelbag-zblack'),(1473243891,'0-NoelBag-green'),(1473243900,'596-NoelBag-zgrey'),(1473243912,'60-NoelBag-black'),(1473243913,'61-NoelBag-beige'),(1473243914,'043-NoelBag-brown'),(1473245510,'590-PamelaBag-brown'),(1535337771,'3-FurPanama-coffee'),(1535337773,'5-FurPanama-beige')]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':print('Already complete');return
 if not v:v=dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT,copy.deepcopy(v))
 ids=[x[0]for x in ITEMS]
 stage('prices',lambda:current_prices(io,ids))
 stage('stock',lambda:read_stock([x[1]for x in ITEMS],warehouse_role='msk'))
 stage('published',lambda:published_stock(io,v['prices'],ids))
 def economics():
  b=io.get('china_agent:advertising_source:2026-11-23:v2')['full_growth_inputs']
  return model_rows(dict(products=b['own'],prices=v['prices'],stock=v['stock'],fx=b['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 stage('economics',economics)
 def funnel():
  body=dict(selectedPeriod={'start':'2026-11-19','end':'2026-11-22'},pastPeriod={'start':'2026-11-12','end':'2026-11-15'},nmIds=ids,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
  r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token},json=body,timeout=(10,55));r.raise_for_status();return dict(request=body,response=r.json(),observed_at=now())
 stage('funnel',funnel)
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()

