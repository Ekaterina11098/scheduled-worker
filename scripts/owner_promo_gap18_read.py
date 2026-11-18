"""Bounded API-only promotion gap screen. No marketplace mutations or Telegram."""
import os,time,json,requests
from urllib.parse import urlparse
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_moysklad_read import Reader
ROOT='china_agent:owner_promo_gap:2026-11-18:v1'
def main():
 c=Cache();assert c.create(ROOT+':claim',dict(status='collecting',at=stamp()))
 v=dict(status='collecting',observed_at=stamp(),errors=[],candidates=[],wb_writes=0,telegram_calls=0,model_calls=0)
 def save():c.put(ROOT,v)
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();p=u.path
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and p.startswith('/rest/v1/') and m in ('GET','POST','PATCH')) or (u.hostname=='api.moysklad.ru' and m=='GET' and p.startswith('/api/remap/1.2/')) or (u.hostname=='advert-api.wildberries.ru' and m=='GET' and p in ('/api/advert/v2/adverts','/api/advert/v1/config')) or (u.hostname=='discounts-prices-api.wildberries.ru' and m=='GET' and p=='/api/v2/list/goods/filter') or (u.hostname=='dp-calendar-api.wildberries.ru' and m=='GET' and p in ('/api/v1/calendar/promotions','/api/v1/calendar/promotions/nomenclatures'))
  assert ok,'Read-only scope rejected '+m+' '+str(u.hostname)+p
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 def get(host,path,params):
  time.sleep(.7);r=requests.get('https://'+host+path,params=params,headers={'Authorization':os.environ['WB_TOKEN_3']},timeout=(8,35));r.raise_for_status();return r.json()
 try:
  validate_identity(c,WB());prices={};price_complete=False
  for offset in (0,1000,2000):
   rows=get('discounts-prices-api.wildberries.ru','/api/v2/list/goods/filter',dict(limit=1000,offset=offset))['data']['listGoods']
   prices.update({int(r['nmID']):r for r in rows})
   if len(rows)<1000:price_complete=True;break
  v.update(price_count=len(prices),prices_complete=price_complete);save()
  promos=get('dp-calendar-api.wildberries.ru','/api/v1/calendar/promotions',dict(startDateTime='2026-11-17T21:00:00Z',endDateTime='2026-11-18T20:59:59Z',allPromo='false'))['data']['promotions']
  v['promotions']=promos;v['promotion_coverage_complete']=len(promos)<=10;seen=set();fur={2215883910,2216045897,2216111729,2216167898,2216217906,2216257724}
  for promo in promos[:10]:
   try:
    raw=get('dp-calendar-api.wildberries.ru','/api/v1/calendar/promotions/nomenclatures',dict(promotionID=promo['id'],inAction='false',limit=1000,offset=0));rows=raw['data']['nomenclatures']
    if len(rows)>=1000:v['promotion_coverage_complete']=False
    for r in rows:
     nm=int(r['id']);g=prices.get(nm)
     if not g or nm in fur or r.get('inAction') is True:continue
     current={float(s['discountedPrice']) for s in g['sizes']}
     if len(current)!=1:continue
     current=current.pop();target=float(r['planPrice']);gap=(current-target)/current*100
     if not 0<gap<=2.000001:continue
     if (nm,target) in seen:continue
     seen.add((nm,target));v['candidates'].append(dict(nm_id=nm,article=g.get('vendorCode'),current_cny=current,target_cny=target,decline_pct=gap,seller_discount=g['discount'],promotion_id=promo['id'],promotion_name=promo['name']))
   except Exception as ex:v['errors'].append(dict(promotion_id=promo['id'],reason=str(ex)[:220]));v['promotion_coverage_complete']=False
   save()
  candidates=sorted(v['candidates'],key=lambda r:r['decline_pct']);v['candidates']=candidates
  source=c.get('china_agent:advertising_source:2026-11-18:v2') or {};econ=source.get('economics',{});v['economics_fields']=list(econ)
  if candidates and len(candidates)<=35:
   stock=Reader().stock(list(dict.fromkeys(r['article'] for r in candidates)),'msk');v['fresh_stock']=stock
   by_article={r['article']:r for r in stock.get('rows',[])}
   for r in candidates:r['fresh_stock_cogs']=by_article.get(r['article']);r['saved_economics']=econ.get('rows',{}).get(str(r['nm_id']))
  v.update(status='complete_with_gaps' if v['errors'] or not v['promotion_coverage_complete'] else 'complete',completed_at=stamp());save()
  print(json.dumps(dict(status=v['status'],price_count=len(prices),candidate_count=len(candidates),errors=v['errors'])))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

