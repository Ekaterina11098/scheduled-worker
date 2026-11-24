import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_moysklad_read import Reader,BASE
from moysklad_warehouses import select_store
ROOT='china_agent:owner_stock_without_ads:2026-11-24:v1'
def now():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();v=io.get(ROOT)
 if v and v.get('status')=='complete':return
 if not v:v=dict(status='reading',observed_at=now(),errors={},wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT,v)
 orig=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/'))or(u.hostname=='advert-api.wildberries.ru'and m=='GET'and u.path in('/adv/v1/promotion/count','/api/advert/v2/adverts'))or(u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and u.path=='/api/v2/list/goods/filter')or(u.hostname=='api.moysklad.ru'and m=='GET'and u.path in('/api/remap/1.2/entity/store','/api/remap/1.2/report/stock/all'))
  assert ok,'Read only MSK inventory and campaign membership';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def stage(k,fn):
  if k in v:return
  try:v[k]=fn();v['errors'].pop(k,None)
  except Exception as ex:v['errors'][k]=type(ex).__name__+': '+str(ex)[:250]
  io.put(ROOT,copy.deepcopy(v))
 def ad(path):
  time.sleep(1.5);r=requests.get('https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()
 stage('inventory',lambda:dict(raw=ad('/adv/v1/promotion/count'),observed_at=now()))
 def campaigns():
  ids=sorted({x['advertId']for g in v['inventory']['raw'].get('adverts',[])if g['status']in(4,9,11)for x in g['advert_list']})
  assert ids
  found=[]
  for i in range(0,len(ids),50):found+=ad('/api/advert/v2/adverts?ids='+','.join(map(str,ids[i:i+50])))['adverts']
  assert {c['id']for c in found}==set(ids)
  return dict(rows=found,observed_at=now(),requested=ids)
 stage('campaigns',campaigns)
 def prices():
  goods=io.wb('/api/v2/list/goods/filter?limit=1000&offset=0')['listGoods'];assert len(goods)<1000
  return dict(rows=[dict(nm_id=g['nmID'],article=g['vendorCode'])for g in goods],observed_at=now())
 stage('catalogue',prices)
 def stock():
  reader=Reader();store=select_store(reader.pages('/entity/store',{}),'msk');assert store['id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
  rows=reader.pages('/report/stock/all',{'filter':'store='+store['meta']['href']+';stockMode=positive;quantityMode=all'})
  out=[]
  for r in rows:
   if not r.get('article'):continue
   assert all(type(r.get(k))in(int,float)for k in('stock','reserve')),'Stock/reserve missing'
   out.append(dict(article=r['article'],stock=r['stock'],reserve=r['reserve'],available=r['stock']-r['reserve'],name=r.get('name'),product_href=r.get('meta',{}).get('href')))
  return dict(rows=out,warehouse_id=store['id'],observed_at=now())
 stage('stock',stock)
 if not v['errors']:
  cat=v['catalogue']['rows'];by_article={}
  # Current China price catalogue establishes the cabinet; historical cached cards only classify missing mappings.
  for c in cat:by_article.setdefault(c['article'].casefold(),[]).append(c)
  members={}
  for c in v['campaigns']['rows']:
   for n in c['nm_settings']:members.setdefault(n['nm_id'],[]).append(dict(cid=c['id'],status=c['status'],name=c['settings']['name']))
  groups={}
  for s in v['stock']['rows']:
   if s['available']>0:groups.setdefault(s['article'].casefold(),[]).append(s)
  absent=[];paused=[];draft=[];covered=[];unmapped=[];ambiguous=[]
  for key,ss in groups.items():
   matches=by_article.get(key,[])
   if len(ss)!=1 or len(matches)>1:ambiguous.append(dict(article=ss[0]['article'],stock_rows=len(ss),card_matches=len(matches)));continue
   if not matches:unmapped.append(ss[0]);continue
   row=dict(ss[0],nm_id=matches[0]['nm_id'],campaigns=members.get(matches[0]['nm_id'],[]))
   if not row['campaigns']:absent.append(row)
   elif any(c['status']==9 for c in row['campaigns']):covered.append(row)
   elif any(c['status']==11 for c in row['campaigns']):paused.append(row)
   else:draft.append(row)
  for a in(absent,paused,draft,covered,unmapped,ambiguous):a.sort(key=lambda r:(-r.get('available',0),r['article']))
  v['result']=dict(absent=absent,paused_only=paused,draft_only=draft,active=covered,unmapped_msk_products=unmapped,ambiguous=ambiguous,warehouse='MSK',free_basis='stock-reserve',catalogue_count=len(cat),active_campaign_count=sum(c['status']==9 for c in v['campaigns']['rows']),paused_campaign_count=sum(c['status']==11 for c in v['campaigns']['rows']),draft_campaign_count=sum(c['status']==4 for c in v['campaigns']['rows']))
 v.update(status='complete'if not v['errors']else'complete_with_gaps',completed_at=now());io.put(ROOT,v)
 print(json.dumps({'status':v['status'],'errors':v['errors'],'counts':{k:len(v.get('result',{}).get(k,[]))for k in('absent','paused_only','draft_only','active','unmapped_msk_products','ambiguous')}}))
if __name__=='__main__':main()
