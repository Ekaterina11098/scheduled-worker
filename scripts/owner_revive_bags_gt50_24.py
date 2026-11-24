import os,json,time,requests,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
ROOT='china_agent:owner_revive_bags_gt50:2026-11-24:v1'
ITEMS=[{"nm_id":1473245495,"article":"144-SamiraBag-brown","available":1053},{"nm_id":1473245508,"article":"587-ReginaBag-orange","available":383},{"nm_id":1473245509,"article":"588-ReginaBag-dbrown","available":324},{"nm_id":1473243089,"article":"511-VivienneBag-grey","available":180},{"nm_id":1473244985,"article":"042-EvaBag-brown","available":129},{"nm_id":1473242758,"article":"40-MichelleBag-grey","available":128},{"nm_id":1473243443,"article":"238-KendraBag-ginger","available":126},{"nm_id":1473244991,"article":"021-AdeleBag-brown","available":111},{"nm_id":1473242583,"article":"647-RoseBag-blue","available":87},{"nm_id":1473242579,"article":"639-FreyaBag-lblue","available":86},{"nm_id":1473245005,"article":"652-RheaBag-beige","available":85},{"nm_id":1473245007,"article":"654-RheaBag-pink","available":83},{"nm_id":1473243454,"article":"552-AriadnaBag-brown","available":75},{"nm_id":1473242581,"article":"645-RoseBag-cream","available":72},{"nm_id":1473245008,"article":"655-RheaBag-green","available":67},{"nm_id":1473242580,"article":"644-RoseBag-white","available":66},{"nm_id":1473244982,"article":"013-ErminiaBag-beige","available":63},{"nm_id":1473245002,"article":"625-AudreyBag-gray","available":63},{"nm_id":1473242768,"article":"462-VesiBag-cream","available":58},{"nm_id":1473243094,"article":"684-CelineaBag-grey","available":57},{"nm_id":1473243090,"article":"680-VivienneBag-black","available":55}]
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':return
 if not v:v=dict(status='reading',scope=ITEMS,errors={},observed_at=now(),wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='api.moysklad.ru'and m=='GET')or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='marketplace-api.wildberries.ru'and m=='POST'and u.path=='/api/v3/stocks/2126188')or(u.hostname=='seller-analytics-api.wildberries.ru'and m=='POST'and u.path=='/api/analytics/v3/sales-funnel/products'and set((kw.get('json')or{}).get('nmIds',[]))=={x['nm_id']for x in ITEMS})or(u.hostname=='advert-api.wildberries.ru'and((m=='GET'and u.path=='/api/advert/v2/adverts')or(m=='POST'and u.path=='/api/advert/v1/bids/min')))
  assert ok,'Exact21bags readonlyscope';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT,copy.deepcopy(v))
 ids=[x['nm_id']for x in ITEMS]
 def prices():
  goods=io.wb('/api/v2/list/goods/filter?limit=1000&offset=0')['listGoods'];assert len(goods)<1000
  rows=[]
  for x in ITEMS:
   p=[p for p in goods if p['nmID']==x['nm_id']];assert len(p)==1
   g=p[0];assert g['vendorCode']==x['article']and g['currencyIsoCode4217']=='CNY';ps={s['discountedPrice']for s in g['sizes']};assert len(ps)==1
   rows.append(dict(nm_id=x['nm_id'],article=x['article'],seller_price=next(iter(ps)),size_ids=[s['sizeID']for s in g['sizes']],raw=g))
  return dict(rows=rows,observed_at=now())
 stage('prices',prices)
 def stock():
  parts=[read_stock([x['article']for x in ITEMS[i:i+20]],warehouse_role='msk')for i in range(0,len(ITEMS),20)]
  assert all(x['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'for x in parts)
  return dict(rows=[r for p in parts for r in p['rows']],missing_articles=[r for p in parts for r in p['missing_articles']],observed_at=now(),warehouse_id=parts[0]['warehouse_id'])
 stage('stock',stock)
 stage('published',lambda:published_stock(io,v['prices'],ids))
 def economics():
  b=io.get('china_agent:advertising_source:2026-11-24:v2')['full_growth_inputs']
  return model_rows(dict(products=b['own'],prices=v['prices'],stock=v['stock'],fx=b['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
 stage('economics',economics)
 def ad(path,body=None):
  time.sleep(1.5);r=requests.request('POST'if body is not None else'GET','https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},json=body,timeout=(10,55));r.raise_for_status();return r.json()
 stage('target_campaigns',lambda:ad('/api/advert/v2/adverts?ids=41332083,41055480,42068228,41298169,41270309'))
 def minimum():
  campaigns=v['target_campaigns']['adverts'];out=[]
  for cid,placement in[(41332083,'search'),(41055480,'recommendation')]:
   c=next(c for c in campaigns if c['id']==cid);n=next(n for n in c['nm_settings']if n['subject']['id']==50)
   out.append(dict(cid=cid,subject_id=50,reference_nm=n['nm_id'],placement=placement,quote=ad('/api/advert/v1/bids/min',dict(advert_id=cid,nm_ids=[n['nm_id']],payment_type='cpc',placement_types=[placement])),observed_at=now(),basis='same_subject_minimum_owner_rule_before_add'))
  return out
 stage('minimum',minimum)
 def funnel(start,end,pstart,pend):
  body=dict(selectedPeriod={'start':start,'end':end},pastPeriod={'start':pstart,'end':pend},nmIds=ids,brandNames=[],subjectIds=[],tagIds=[],skipDeletedNm=False,orderBy={'field':'openCard','mode':'desc'},limit=100,offset=0)
  time.sleep(22);r=requests.post('https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products',headers={'Authorization':io.token},json=body,timeout=(10,55));r.raise_for_status();return dict(request=body,response=r.json(),observed_at=now())
 stage('funnel7',lambda:funnel('2026-11-17','2026-11-23','2026-11-10','2026-11-16'))
 stage('funnel4',lambda:funnel('2026-11-20','2026-11-23','2026-11-16','2026-11-19'))
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());io.put(ROOT,v);print(json.dumps(dict(status=v['status'],errors=v['errors'],economy_missing=v.get('economics',{}).get('missing'))))
if __name__=='__main__':main()
