import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_raise_review:2026-11-24:v1'
ITEMS=[{"nm":1473243827,"article":"56-NoelBag-cream"},{"nm":1473243891,"article":"0-NoelBag-green"},{"nm":1473243898,"article":"119-NoelBag-darkblack"},{"nm":1473243900,"article":"596-NoelBag-zgrey"},{"nm":1473243906,"article":"51-NoelBag-green"},{"nm":1473243910,"article":"58-NoelBag-brown"},{"nm":1473243912,"article":"60-NoelBag-black"},{"nm":1473243914,"article":"043-NoelBag-brown"},{"nm":1473243915,"article":"63-NoelBag-zdarkblue"},{"nm":1473243918,"article":"67-NoelBag-zginger"},{"nm":1535337769,"article":"1-FurPanama-grey"},{"nm":1535337771,"article":"3-FurPanama-coffee"},{"nm":1556488202,"article":"92-Zont-red"}]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':print('Complete, no repeated reads');return
 if not v:v=dict(status='reading',scope=ITEMS,warehouse='msk',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.moysklad.ru'and m=='GET')or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and u.path=='/api/v3/stocks/2126188')or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='POST'and u.path=='/api/analytics/v3/sales-funnel/products'and set((kw.get('json')or{}).get('nmIds',[]))=={x['nm']for x in ITEMS})
  assert ok,'Read-only exact MSK price review scope';return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def stage(key,fn):
  if key in v:return
  try:v[key]=fn();v['errors'].pop(key,None)
  except Exception as ex:v['errors'][key]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT,copy.deepcopy(v))
 ids=[x['nm']for x in ITEMS]
 def prices():
  allgoods=io.wb('/api/v2/list/goods/filter?limit=1000&offset=0')['listGoods'];assert len(allgoods)<1000
  rows=[]
  for x in ITEMS:
   goods=[g for g in allgoods if g['nmID']==x['nm']];assert len(goods)==1
   g=goods[0];assert g['currencyIsoCode4217']=='CNY'and g['vendorCode']==x['article'];ps={s['discountedPrice']for s in g['sizes']};assert len(ps)==1
   rows.append(dict(nm_id=x['nm'],article=x['article'],seller_price=next(iter(ps)),size_ids=[s['sizeID']for s in g['sizes']],raw=g))
  return dict(rows=rows,observed_at=now())
 stage('prices',prices)
 stage('stock',lambda:read_stock([x['article']for x in ITEMS],warehouse_role='msk'))
 stage('published',lambda:published_stock(io,v['prices'],ids))
 def economics():
  b=io.get('china_agent:advertising_source:2026-11-24:v2')['full_growth_inputs']
  return model_rows(dict(products=b['own'],prices=v['prices'],stock=v['stock'],fx=b['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 stage('economics',economics)
 def funnel(start,end,pstart,pend):
  body=dict(selectedPeriod={'start':start,'end':end},pastPeriod={'start':pstart,'end':pend},nmIds=ids,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
  time.sleep(22);r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token},json=body,timeout=(10,55));r.raise_for_status();return dict(request=body,response=r.json(),observed_at=now())
 stage('funnel4',lambda:funnel('2026-11-20','2026-11-23','2026-11-16','2026-11-19'))
 stage('funnel7',lambda:funnel('2026-11-17','2026-11-23','2026-11-10','2026-11-16'))
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'],candidate_scope=len(ITEMS))))
if __name__=='__main__':main()
