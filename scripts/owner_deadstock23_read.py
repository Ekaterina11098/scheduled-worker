import os,json,time,copy,requests
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_deadstock:2026-11-23:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();scope=io.get(ROOT+':scope');assert scope['status']=='authorized_read_only'and scope['owner_id']==5122667182
 v=io.get(ROOT+':fresh')
 if v and v['status']=='complete':print('Already complete');return
 if not v:v=dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':fresh',v)
 def save():io.put(ROOT+':fresh',copy.deepcopy(v))
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:300]
  save()
 def post(host,path,body):
  time.sleep(1.3);r=requests.post('https://'+host+path,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},json=body,timeout=(10,60));r.raise_for_status();return r.json()
 def extra():
  j=post('content-api.wildberries.ru','/content/v2/get/cards/list',{'settings':{'cursor':{'limit':100},'filter':{'textSearch':'018-JuneBag','withPhoto':-1}}});return [c for c in j['cards']if c['vendorCode'].startswith('018-JuneBag')]
 stage('extra_card',extra);items=copy.deepcopy(scope['items'])
 for c in v.get('extra_card',[]):items.append(dict(nm_id=c['nmID'],article=c['vendorCode']))
 v['items']=items;ids=[x['nm_id']for x in items];articles=[x['article']for x in items]
 if len(items)==24:articles.append(scope['extra_article'])
 stage('prices',lambda:current_prices(io,ids));stage('stock',lambda:read_stock(articles,warehouse_role='msk'));stage('published',lambda:published_stock(io,v['prices'],ids))
 def funnel():
  body=dict(selectedPeriod={'start':'2026-11-16','end':'2026-11-22'},pastPeriod={'start':'2026-11-09','end':'2026-11-15'},nmIds=ids,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
  return dict(observed_at=now(),request=body,response=post('seller-analytics-api.wildberries.ru','/api/analytics/v3/sales-funnel/products',body))
 stage('funnel',funnel)
 def economics():
  s=io.get('china_agent:advertising_source:2026-11-23:v2');b=s['full_growth_inputs'];v['saved_own']=dict(b['own'],rows=[r for r in b['own']['rows']if r['nm_id']in ids]);result=model_rows(dict(products=b['own'],prices=v['prices'],stock=v['stock'],fx=b['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
  for row in result['rows'].values():
   if row.get('buyout_fallback')and row.get('sample_size')==0:
    row['buyout']=.4;row['planned_buyout_source']='owner-approved-bags40';fee=1-sum(row[k]for k in('commission_pct','tax_pct','payment_reserve_pct'))/100;row['expected_margin_before_ads_cny']=.4*(row['seller_price_cny']*fee-row['own_cogs_rub']/row['fx_rub_per_cny'])-row['logistics_cny']-row.get('handling_rub',0)/row['fx_rub_per_cny']
  return result
 stage('economics',economics)
 def blocked():
  r=requests.get('https://seller-analytics-api.wildberries.ru/api/v1/analytics/banned-products/blocked',params={'sort':'nmId','order':'asc'},headers={'Authorization':io.token},timeout=(10,55));r.raise_for_status();return [x for x in r.json()['report']if x['nmId']in ids]
 stage('blocked',blocked)
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());save();print(json.dumps(dict(status=v['status'],errors=v['errors'],items=len(items))))
if __name__=='__main__':main()