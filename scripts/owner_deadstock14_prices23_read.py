import json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_deadstock_prices:2026-11-23:v1'
SCOPE=[{"nm_id":1473242756,"article":"84-CamilaBag-green","before_price":334.1},{"nm_id":1473242754,"article":"98-EmmaBag-ginger","before_price":434.5},{"nm_id":1473246033,"article":"439-SophieBag-cream","before_price":453.7},{"nm_id":1473244987,"article":"110-GretaBag-beige","before_price":206.7},{"nm_id":1473244988,"article":"024-SilviaBag-gray","before_price":187.59},{"nm_id":1473242768,"article":"462-VesiBag-cream","before_price":382.2},{"nm_id":1473242753,"article":"29-JaniceBag-brown","before_price":342.16},{"nm_id":1473245493,"article":"142-ArinaBag-brown","before_price":420},{"nm_id":1473242762,"article":"35-ElsaBag-brown","before_price":259.5},{"nm_id":1473245498,"article":"210-SamiraBag-cream","before_price":350.5},{"nm_id":1473245499,"article":"282-KiraBag-gray","before_price":400},{"nm_id":1473243933,"article":"402-NillyBag-beige","before_price":264},{"nm_id":1473242758,"article":"40-MichelleBag-grey","before_price":362.7},{"nm_id":1473244982,"article":"013-ErminiaBag-beige","before_price":273}]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v['status']=='verified':print('Already verified');return
 if not v:
  v=dict(status='reading',observed_at=now(),rows={},errors={},wb_writes=0,telegram_calls=0,model_calls=0,change_day_msk='2026-11-23',first_full_day_msk='2026-11-24',earliest_full_day_review_msk='2026-11-25',ordinary_review_days=['2026-11-24','2026-11-25','2026-11-26'])
  assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in ('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter');assert ok,'Price-read-only scope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 for x in SCOPE:
  nm=x['nm_id'];key=str(nm)
  if key in v['rows']:continue
  try:
   time.sleep(1.5);r=requests.get('https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter',params=dict(limit=100,offset=0,filterNmID=nm),headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();j=r.json();assert not j.get('error');goods=j['data']['listGoods'];assert len(goods)==1 and goods[0]['nmID']==nm and goods[0]['vendorCode']==x['article']and goods[0]['currencyIsoCode4217']=='CNY';g=goods[0];assert len(g['sizes'])==1;size=g['sizes'][0];p=size['discountedPrice'];assert abs(size['price']*(1-g['discount']/100)-p)<.011
   v['rows'][key]=dict(x,status='verified',observed_at=now(),raw=g,base_cny=size['price'],seller_discount_pct=g['discount'],price_cny=p,club_price_cny=size.get('clubDiscountedPrice'),club_discount_pct=g.get('clubDiscount'),source='WB Prices API; owner manual change',changed=p!=x['before_price']);v['errors'].pop(key,None)
  except Exception as ex:v['errors'][key]=type(ex).__name__+': '+str(ex)[:200]
  io.put(ROOT,v)
 for key,row in v['rows'].items():
  if row['changed']:io.create('china_agent:experience:v1:owner-deadstock23-price-'+key,dict(status='verified',started_at=row['observed_at'],change_day_msk='2026-11-23',source='owner_manual_change_WB_readback',execution_key=ROOT,action=dict(kind='price_change',nm_ids=[int(key)],before=row['before_price'],after=row['price_cny'])))
 v.update(status='verified'if len(v['rows'])==14 and not v['errors']else'complete_with_gaps',completed_at=now(),experience_registered=True,minimum_prices_verified=False);io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'])))
if __name__=='__main__':main()
