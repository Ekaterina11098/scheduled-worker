"""One exact requested evidence refresh. GET only; no ad writes, funding or Telegram."""
import base64,collections,datetime,hashlib,json,os,time
import requests
from china_codex_cloud import DB,stamp
from china_moysklad_read import Reader,MoySkladReadError,BASE
ROOT='ooo_agent:growth_sales_review:2026-11-27:v1'
HOST='statistics-api.wildberries.ru'

def summarize(orders,sales,ids):
 latest={}
 for row in sales:
  if not row.get('srid'):continue
  event=(row.get('lastChangeDate',''),row.get('date',''),str(row.get('saleID','')).startswith('R'))
  if event>=latest.get(row['srid'],('','','')):latest[row['srid']]=event
 out={}
 for name,start,end in [('old_comparable','2026-10-05','2026-10-28'),('mature_recent','2026-10-19','2026-11-13'),('recent_unmatured','2026-11-14','2026-11-26'),('combined','2026-10-19','2026-11-26')]:
  values={nm:collections.Counter()for nm in ids};unique={}
  for row in orders:
   if row.get('srid')and start<=row.get('date','')[:10]<=end:
    if row.get('lastChangeDate','')>=unique.get(row['srid'],{}).get('lastChangeDate',''):unique[row['srid']]=row
  for srid,row in unique.items():
   v=values[row['nmId']];v['ordered']+=1
   if srid in latest:v['returned'if latest[srid][2]else'paid']+=1;v['closed']+=1
   elif row.get('isCancel'):v['cancelled']+=1;v['closed']+=1
   else:v['unresolved']+=1
  out[name]={'from':start,'to':end,'rows':[{'nm':nm,**dict(v)}for nm,v in values.items()]}
 return out

def main():
 db=DB();auth=db.get(ROOT+':request')or{}
 if auth.get('status')!='approved_read_only'or auth.get('cabinet')!='token_1'or len(auth.get('products',[]))!=4:raise PermissionError('Exact 27-item read approval required')
 if(db.get(ROOT+':summary')or{}).get('status')=='complete':print('Existing complete evidence retained; no duplicate reads');return
 ids={v['nm']for v in auth['products']};articles=[v['article']for v in auth['products']]
 token=os.environ['WB_TOKEN_1'];claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
 identity=db.api('GET','analytics_snapshots',{'cabinet':'eq.token_1','source':'eq.seller_identity','status':'eq.complete','select':'payload','limit':100})
 if claims.get('exp',0)<=time.time()or claims.get('t')is not False or int(claims.get('s',0))&(1<<30)or not claims.get('sid')or{r['payload'].get('sid')for r in identity}!={claims['sid']}:raise PermissionError('OOO identity mismatch')
 def stage(kind):
  key=ROOT+':'+kind;old=db.get(key)or{}
  if old.get('status')=='complete':return old['rows']
  path='/api/v1/supplier/'+kind
  if kind not in('orders','sales'):raise PermissionError('Read endpoint denied')
  pausekey='wb-pause:'+hashlib.sha256((token+HOST+path).encode()).hexdigest()
  for attempt in range(4):
   wait=float((db.get(pausekey)or{}).get('until',0))-time.time()
   while wait>0:time.sleep(min(30,wait+.1));wait=float((db.get(pausekey)or{}).get('until',0))-time.time()
   response=requests.get('https://'+HOST+path,params={'dateFrom':'2026-10-05T00:00:00','flag':0},headers={'Authorization':token},timeout=(10,90),allow_redirects=False)
   try:delay=float(response.headers.get('Retry-After')or response.headers.get('X-Ratelimit-Retry')or 60)
   except ValueError:delay=60
   if delay>time.time()-86400:delay=max(0,delay-time.time())
   if response.status_code==429 or response.headers.get('X-Ratelimit-Remaining')=='0':
    value={'until':time.time()+max(60,delay)+3,'basis':'provider_header'};db.update(pausekey,value)if db.get(pausekey)else db.once(pausekey,value)
   if response.status_code==429:continue
   if response.status_code!=200:raise RuntimeError('Read '+kind+' HTTP '+str(response.status_code))
   rows=response.json()
   if not isinstance(rows,list)or len(rows)>=80000:raise RuntimeError('Incomplete source; analysis denied')
   fields=['srid','nmId','date','lastChangeDate','isCancel']if kind=='orders'else['srid','nmId','date','lastChangeDate','saleID']
   filtered=[{k:r.get(k)for k in fields}for r in rows if r.get('nmId')in ids]
   value={'status':'complete','dateFrom':'2026-10-05','provider_rows':len(rows),'observed_at':stamp(),'rows':filtered}
   db.update(key,value)if old else db.once(key,value);return filtered
  raise RuntimeError('Read quota pending; stages retained')
 class CostReader(Reader):
  def __init__(self):super().__init__();self.products=[]
  def get(self,path,params):
   if path!='/entity/currency':return super().get(path,params)
   r=requests.get(BASE+path,params=params,headers={'Authorization':'Bearer '+self.token,'Accept-Encoding':'gzip','Accept':'application/json;charset=utf-8'},timeout=(10,40),allow_redirects=False)
   if r.status_code!=200:raise MoySkladReadError('Currency read HTTP '+str(r.status_code))
   return r.json()
  def pages(self,path,params):
   value=super().pages(path,params)
   if path=='/entity/product':self.products+=value
   return value
 msk=db.get(ROOT+':moysklad')or{}
 if msk.get('status')!='complete':
  reader=CostReader();stock=reader.stock(articles)
  if not stock['coverage_complete']:raise RuntimeError('Exact stock coverage incomplete')
  currencies={v['meta']['href']:v for v in reader.pages('/entity/currency',{})}
  cards=[]
  for article in articles:
   matched=[v for v in reader.products if str(v.get('article','')).casefold()==article.casefold()]
   if len(matched)!=1:raise RuntimeError('Exact product identity ambiguous')
   p=matched[0];buy=p.get('buyPrice',{});currency=currencies.get(buy.get('currency',{}).get('meta',{}).get('href'),{})
   cards.append({'article':article,'updated':p.get('updated'),'archived':p.get('archived'),'buy_price_minor':buy.get('value'),'buy_price_iso':currency.get('isoCode'),'buy_price_currency_code':currency.get('code')})
  msk={'currencies':[{k:v.get(k)for k in ['isoCode','code','default','rate','multiplicity','indirect']}for v in currencies.values()],'status':'complete','observed_at':stamp(),'stock':stock,'products':cards,'moysklad_writes':0}
  db.update(ROOT+':moysklad',msk)if db.get(ROOT+':moysklad')else db.once(ROOT+':moysklad',msk)
 orders=stage('orders');sales=stage('sales')
 value={'status':'complete','cabinet':'token_1','observed_at':stamp(),'products':auth['products'],'cohorts':summarize(orders,sales,ids),'moysklad_key':ROOT+':moysklad','wb_writes':0,'moysklad_writes':0,'telegram_calls':0,'model_calls':0}
 db.once(ROOT+':summary',value);print('Exact 27-SKU matched cohorts and current cost cards saved privately; no mutations/delivery')
if __name__=='__main__':main()
