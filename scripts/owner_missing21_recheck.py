"""Fresh exact21 COGS and two-warehouse availability audit; no mutations."""
import os,json,copy,time,requests,re
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices
from china_moysklad_read import Reader,BASE
ROOT='china_agent:owner_missing21_recheck:2026-11-21:v1'
ITEMS={1473243451:'543-AnikaBag-coffee',1473242770:'472-StellaBag-beige',1473244335:'123-EmraBag-black',1473243441:'153-ConsuelaBag-black',1900202932:'482-RiginaBag-red',1473244348:'602-JessicaBag-green',2129309884:'160-CelineaBag-burgundy',1900197978:'145-FlorenceBag-black',1473244350:'600-JessicaBag-blue',1473245503:'525-SamiraBag-ginger',1473245000:'614-MayaBag-black',1473243456:'615-MayaBag-brown',1473243457:'616-MayaBag-black',1560345289:'38-FurManizhka-white',1560345288:'37-FurManizhka-dbrown',1473244990:'020-AdeleBag-black',1473244984:'023-AlessiaBag-black',1556488196:'53-Zont-Ifio',1535337774:'6-FurPanama-burgundy',1556488037:'57-Zont-fio',1556488190:'23-Zont-pink'}
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)or dict(status='collecting',created_at=now(),wb_writes=0,telegram_calls=0,model_calls=0,scope=ITEMS)
 if v['status']=='complete':print('Already complete');return
 def save():
  v['updated_at']=now()
  payload=json.loads(json.dumps(v,ensure_ascii=False))
  io.put(ROOT,payload)if io.get(ROOT)else io.create(ROOT,payload)
 orig=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or''
  if host=='api.telegram.org'or'openai'in host:raise ValueError('No Telegram/model')
  if host.endswith('wildberries.ru'):assert (m=='GET'and u.path=='/api/v2/list/goods/filter')or(m=='POST'and u.path in('/api/v3/stocks/2126188','/api/v3/stocks/2373413')),'No WB mutations'
  if host.endswith('moysklad.ru'):assert m=='GET','No stock writes'
  return orig(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 if 'prices'not in v:v['prices']=current_prices(io,sorted(ITEMS));save()
 assert {p['nm_id']for p in v['prices']['rows']}==set(ITEMS)
 assert all(p['article']==ITEMS[p['nm_id']]for p in v['prices']['rows'])
 class CachedReader(Reader):
  def __init__(self):super().__init__();self.memo={};self.products=[]
  def pages(self,path,params):
   if path in('/entity/store','/entity/product'):
    key=path+json.dumps(params,sort_keys=True)
    if key not in self.memo:
     self.memo[key]=super().pages(path,params)
     if path=='/entity/product':self.products+=self.memo[key]
    return copy.deepcopy(self.memo[key])
   return super().pages(path,params)
 reader=CachedReader();arts=list(ITEMS.values())
 for role in ('msk','guangzhou'):
  if role+'_stock'not in v:
   chunks=[reader.stock(arts[i:i+20],warehouse_role=role)for i in range(0,len(arts),20)]
   v[role+'_stock']=dict(rows=[r for c in chunks for r in c['rows']],missing_articles=[r for c in chunks for r in c['missing_articles']],warehouse_id=chunks[0]['warehouse_id'],warehouse=chunks[0]['warehouse'],observed_at=chunks[-1]['observed_at'],coverage_complete=all(c['coverage_complete']for c in chunks));save()
 if 'global_cost'not in v:
  if not reader.products:
   for art in arts:reader.products+=reader.pages('/entity/product',{'filter':'article='+art})
  products={art:[p for p in reader.products if p.get('article')==art]for art in arts}
  matched={a:ps[0]for a,ps in products.items()if len(ps)==1}
  rows=[]
  for start in range(0,len(matched),20):
   group=list(matched.values())[start:start+20];hrefs=[p['meta']['href']for p in group]
   filt='stockMode=all;quantityMode=all'+''.join(';product='+h for h in hrefs)
   rr=reader.pages('/report/stock/all',{'filter':filt});assert all(r['meta']['href'].split('?')[0]in hrefs for r in rr)
   rows.extend({k:r.get(k)for k in('article','stock','reserve','price')}for r in rr)
  v['global_cost']=dict(rows=rows,observed_at=now())
  v['purchase_prices']={a:dict(value=p.get('buyPrice',{}).get('value'),currency_href=p.get('buyPrice',{}).get('currency',{}).get('meta',{}).get('href'))for a,p in matched.items()}
  # Purchase prices are supplementary only; do not silently replace valuation or infer their currency.
  save()
 mapping={str(sz):p['nm_id']for p in v['prices']['rows']for sz in p['size_ids']}
 for role,wid in [('msk',2126188),('guangzhou',2373413)]:
  if role+'_published'not in v:
   r=requests.post('https://marketplace-api.wildberries.ru/api/v3/stocks/'+str(wid),headers={'Authorization':io.token},json={'chrtIds':[int(x)for x in mapping]},timeout=50);r.raise_for_status();raw=r.json();returned={str(x.get('chrtId',x.get('chrtID'))):x['amount']for x in raw.get('stocks',[])}
   assert set(returned)<=set(mapping)
   amounts={};missing=[]
   for nm in ITEMS:
    sizes=[s for s,n in mapping.items()if n==nm]
    if all(s in returned for s in sizes):amounts[str(nm)]=sum(returned[s]for s in sizes)
    else:missing.append(nm)
   v[role+'_published']=dict(warehouse_id=wid,amounts=amounts,missing_nm_ids=missing,observed_at=now());save()
 globalrows={r['article']:r for r in v['global_cost']['rows']};prices={p['nm_id']:p for p in v['prices']['rows']};out=[]
 for nm,art in ITEMS.items():
  item=dict(nm_id=nm,article=art,seller_price_cny=prices[nm]['seller_price'],purchase_price=v['purchase_prices'].get(art))
  for role in ('msk','guangzhou'):
   matches=[r for r in v[role+'_stock']['rows']if r['article']==art];row=matches[0]if len(matches)==1 else{}
   cost=row.get('price');globalcost=globalrows.get(art,{}).get('price')
   valuation=cost/100 if type(cost)in(int,float)and cost>0 else globalcost/100 if type(globalcost)in(int,float)and globalcost>0 else None
   item[role]=dict(stock=row.get('stock'),reserve=row.get('reserve'),free=row['stock']-row['reserve']if type(row.get('stock'))in(int,float)and type(row.get('reserve'))in(int,float)else None,published=v[role+'_published']['amounts'].get(str(nm)),cogs_rub=valuation,cogs_source='warehouse_valuation'if type(cost)in(int,float)and cost>0 else'global_same_product_valuation'if valuation is not None else'unconfirmed',warehouse_valuation_rub=cost/100 if type(cost)in(int,float)else None,global_valuation_rub=globalcost/100 if type(globalcost)in(int,float)else None)
  item['available_routes']=[role for role in ('msk','guangzhou')if item[role]['free']is not None and item[role]['free']>0 and item[role]['published']is not None and item[role]['published']>0]
  item['cost_and_availability_confirmed']=[role for role in item['available_routes']if item[role]['cogs_rub']is not None]
  out.append(item)
 v.update(status='complete',rows=out,completed_at=now());save()
 print(json.dumps(dict(status=v['status'],count=len(out),ready=sum(bool(x['cost_and_availability_confirmed'])for x in out),wb_writes=0,telegram_calls=0)))
if __name__=='__main__':main()
