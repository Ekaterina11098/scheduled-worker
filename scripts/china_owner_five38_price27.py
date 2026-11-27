"""Exact owner47 price targets, durable standard executor; no TG/ads/stock/funding."""
import os,json,time,hashlib,requests
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
import china_price_apply as standard_prices
from china_price_apply import process,PREFIX,POLICY,day,plan
ROOT='china_agent:owner_five38_price27:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def main():
 cache=Cache();a=cache.get(ROOT+':approval');intent=cache.get(ROOT+':intent')
 assert a['status']=='approved'and a['owner_id']==5122667182 and len(intent['items'])==5
 assert len({i['nm_id']for i in intent['items']})==5
 assert all(a[k]is False for k in('advertising_writes','stock_writes','funding_writes','telegram_notifications'))
 def authority():
  assert cache.get(ROOT+':approval')==a and cache.get(ROOT+':intent')==intent
  assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority()
 assert a.get('explicit_exact_targets_override_first_decrease_cap')is True
 exact={str(i['nm_id']):i for i in intent['items']}
 def approved_plan(s,p):
  authority();i=exact[s['nm_id']]
  assert i['article']==s['article']and Decimal(i['target_cny'])==Decimal(s['target_cny'])
  assert str(p['nmID'])==s['nm_id']and p['vendorCode']==s['article']and p['currencyIsoCode4217']=='CNY'and p['editableSizePrice']is False
  assert p['discount']==i['seller_discount']==s['seller_discount']and p.get('clubDiscount')==i['club_discount']==s['club_discount']
  assert p['sizes']and len({Decimal(str(z['price']))for z in p['sizes']})==1 and len({Decimal(str(z['discountedPrice']))for z in p['sizes']})==1
  current=Decimal(str(p['sizes'][0]['discountedPrice']));target=Decimal(i['target_cny'])
  if current==target:return None
  assert current==Decimal(i['current_cny'])==Decimal(s['current_cny'])and Decimal(str(p['sizes'][0]['price']))==Decimal(s['base_cny'])
  base=int(i['base_cny']);assert 1<=base<=100000000 and 0<target<current and Decimal(base)*Decimal(100-p['discount'])/100==target
  return dict(nmID=int(s['nm_id']),price=base,discount=p['discount'])
 standard_prices.plan=approved_plan
 global plan
 plan=approved_plan
 validate_identity(cache,WB())
 if cache.get(ROOT+':execution'):raise ValueError('Existing journal: readback only, no repeat')
 e=dict(status='preflight',created_at=stamp(),wb_writes=0,telegram_calls=0,advertising_writes=0,stock_writes=0,funding_writes=0,model_calls=0,skipped=[],already=[],batch_results=[])
 assert cache.create(ROOT+':execution',e)
 def save():cache.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;expected={}
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();p=u.path;b=kw.get('json')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=p.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='discounts-prices-api.wildberries.ru':
   ok=m=='GET'and p in('/ping','/api/v2/list/goods/filter','/api/v2/history/tasks','/api/v2/history/goods/task')
   if m=='POST':
    ok=p=='/api/v2/upload/task'and isinstance(b,dict)and set(b)=={'data'}and 1<=len(b['data'])<=5 and len({x['nmID']for x in b['data']})==len(b['data'])and all(expected.get(x['nmID'])==x for x in b['data'])
    assert ok,'Outside exact5 targets';authority();used={z['nmID']for old in e.get('submitted_bodies',[])for z in old['data']};assert not used.intersection(z['nmID']for z in b['data']),'Repeated upload blocked'
    e['submitted_at']=stamp();e.setdefault('submitted_bodies',[]).append(b);save()
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and p.startswith('/api/remap/1.2/')
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and p=='/api/v3/stocks/2126188'
  else:ok=False
  assert ok,'Only exact price reads and approved upload';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 class OwnerIO(AdvertisingIO):
  def validate(self,approval):authority();assert approval['owner_approval_key']==ROOT+':approval'and approval['selections']==self.selections
  def tg(self,*args,**kw):raise RuntimeError('Telegram prohibited')
  def prices(self,ids):
   wanted={str(n)for n in ids};found={}
   for offset in range(0,3000,1000):
    rows=self.wb('/api/v2/list/goods/filter?limit=1000&offset='+str(offset)).get('listGoods');assert isinstance(rows,list)
    for r in rows:
     if str(r['nmID'])in wanted:assert str(r['nmID'])not in found;found[str(r['nmID'])]=r
    if len(rows)<1000:break
   return found
 io=OwnerIO()
 try:
  io.capability();goods=io.prices([i['nm_id']for i in intent['items']]);e['before']=goods;save();selections=[]
  for i in intent['items']:
   n=str(i['nm_id']);g=goods.get(n);reason=None
   if not g:reason='WB_price_missing'
   elif g.get('vendorCode')!=i['article']or g.get('currencyIsoCode4217')!='CNY'or g.get('editableSizePrice')is not False:reason='WB_identity_currency_or_size'
   elif g.get('discount')!=i['seller_discount']or g.get('clubDiscount')!=i['club_discount']:reason='Discount changed since proposal'
   elif len({str(z['discountedPrice'])for z in g['sizes']})!=1:reason='Ambiguous sizes'
   if reason:e['skipped'].append(dict(**i,reason=reason));continue
   old=Decimal(str(g['sizes'][0]['discountedPrice']));target=Decimal(i['target_cny'])
   if old==target:e['already'].append(dict(**i,status='already_at_target',readback=g));continue
   if old!=Decimal(i['current_cny']):e['skipped'].append(dict(**i,reason='Current price changed; no repeated or stale cut',actual=str(old)));continue
   assert 0<target<old
   s=dict(nm_id=n,article=i['article'],current_cny=str(old),target_cny=str(target),base_cny=str(g['sizes'][0]['price']),seller_discount=g['discount'],club_discount=g.get('clubDiscount'),action='Снижение')
   body=plan(s,g);assert body==dict(nmID=int(n),price=int(i['base_cny']),discount=i['seller_discount']);expected[int(n)]=body;selections.append(s)
  e.update(items=selections,status='prepared');save()
  from china_moysklad_read import Reader
  from china_morning_readiness import current_prices,published_stock
  stocks=Reader().stock([i['article']for i in intent['items']],'msk');assert stocks['coverage_complete']
  prices=current_prices(io,[i['nm_id']for i in intent['items']]);published=published_stock(io,prices,[i['nm_id']for i in intent['items']]);assert not published['missing_nm_ids']
  cur=requests.get('https://api.moysklad.ru/api/remap/1.2/entity/currency',headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip'},timeout=(10,40));cur.raise_for_status();cur=cur.json()
  assert len([r for r in cur['rows']if r.get('default')])==1 and next(r for r in cur['rows']if r.get('default'))['isoCode']=='CNY'
  inp=io.get('china_agent:advertising_full_growth:2026-11-26:v1:inputs:midday');economics={}
  for i in intent['items']:
   n=str(i['nm_id']);m=inp['economics']['rows'][n];st=next(r for r in stocks['rows']if r['article'].casefold()==i['article'].casefold())
   assert st['stock']-st['reserve']>0 and published['amounts'][n]>0,'Unavailable selected product'
   target=float(i['target_cny']);profit=m['buyout']*(target*(1-(m['commission_pct']+m['tax_pct']+m['payment_reserve_pct'])/100)-st['price']/100)-m['logistics_cny']-m['handling_rub']/m['fx_rub_per_cny']-.08*target
   assert profit>0,'Nonpositive planned DRR8 model'
   economics[n]=dict(profit_at_drr8_cny=profit,price_cny=target,cost_cny=st['price']/100,buyout=m['buyout'],sample_size=m['sample_size'],buyout_fallback=m['buyout_fallback'],preliminary=True)
  e['preflight']=dict(stock=stocks,published=published,currency_aware_economics=economics,observed_at=stamp());save()
  verified=[];execution_key=None
  if selections:
   io.selections=selections;key=PREFIX+'-1004342917488:0:5122667182:'+digest(selections);execution_key='china_agent:price_execution:v1:'+key[len(PREFIX):]
   approval=dict(schema_version=2,execution_authorized=True,execution_policy=POLICY,approval_policy='all_current_human_group_members',decision='approved_recommendation',chat_id=-1004342917488,bot_id=8780468043,report_job_id=0,report_date=day(),actor_user_id=5122667182,created_at=stamp(),selections=selections,owner_approval_key=ROOT+':approval',basis='explicit_owner_exact5_checkout_prices',telegram_notifications=False)
   assert io.create(key,approval),'Existing batch; no replay';e.update(status='running',active_execution_key=execution_key);save();result=process(io,key,polls=12);e['batch_results'].append(dict(execution_key=execution_key,result=result));e['wb_writes']=int(bool(result.get('upload_id')));save()
   assert result['status']=='done','Uncertain upload; readback without replay'
   for x in result['items']:
    if x['status']in('applied','already_at_target'):verified.append(x)
    elif x['status']=='blocked':e['skipped'].append(dict(**x['selection'],reason=x.get('reason','blocked')))
    else:raise ValueError('Unverified item')
  after=io.prices([i['nm_id']for i in intent['items']]);second=io.prices([i['nm_id']for i in intent['items']]);at=stamp()
  from china_experiment_journal import receipt_changes
  for x in verified:
   s=x['selection'];n=s['nm_id']
   for rr in(after,second):
    g=rr[n];assert g['vendorCode']==s['article']and g['discount']==s['seller_discount']and g.get('clubDiscount')==s['club_discount']and g['currencyIsoCode4217']=='CNY'
    assert all(Decimal(str(z['discountedPrice']))==Decimal(s['target_cny'])and Decimal(str(z['price']))==Decimal(expected[int(n)]['price'])for z in g['sizes'])
   rk=ROOT+':item:'+n;rec=dict(status='verified',kind='price_change',cabinet='token_3',before=goods[n],after=second[n],submitted_at=e.get('submitted_at',at),verified_at=at,approval_key=ROOT+':approval',price_execution_key=execution_key,canonical_execution_key=ROOT+':execution',telegram_allowed=False)
   assert io.create(rk,rec);assert receipt_changes(rk,rec)
  snap=io.get('china_agent:prices:v1')or{};merged={str(g['nmID']):g for g in snap.get('rows',[])};merged.update(second);snap.update(rows=list(merged.values()),cabinet='token_3',observed_at=at,source='owner_five38_price27_verified',execution_key=ROOT+':execution');io.put('china_agent:prices:v1',snap)
  changed=datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=3))).date()
  tracking=dict(status='active',canonical_execution_key=ROOT+':execution',items=[x['selection']for x in verified],first_complete_msk_day=str(changed+timedelta(days=1)),first_early_review_msk_day=str(changed+timedelta(days=2)),normal_review_msk_day=str(changed+timedelta(days=4)),existing_hourly_collection=True,new_monitor=False,auto_changes=False,auto_revert_authorized=False,owner_price_override=True)
  assert io.create(ROOT+':tracking',tracking);assert len(verified)+len(e['already'])+len(e['skipped'])==5
  e.update(status='verified'if not e['skipped']else'partial_verified',verified_items=verified,after=second,verified_at=at,reporting_registered=True);save();print(json.dumps(dict(status=e['status'],changed=len(verified),already=len(e['already']),skipped=len(e['skipped']),wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:
  e.update(status='needs_readback'if e.get('submitted_at')else'blocked',reason=type(ex).__name__+': '+str(ex)[:240]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()


