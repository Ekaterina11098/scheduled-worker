"""Six exact prospectively approved price tests; standard durable price engine, no TG/ads/funding."""
import os,json,time,copy,hashlib,requests
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_price_apply import process,PREFIX,POLICY,day,plan
from china_moysklad_read import Reader
from china_advertising_economic_review import model_rows
from china_morning_readiness import published_stock
ROOT='china_agent:owner_remaining25_prices:2026-11-25:v1'
IDS={1473244359,1473243908,1473243910,1473243912,1473243818,1473243825}
def stamp():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def main():
 cache=Cache();a=cache.get(ROOT+':approval');p=cache.get(ROOT+':proposal')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['proposal_sha256']==digest(p)
 assert len(p['items'])==6 and{r['nm_id']for r in p['items']}==IDS and p['target_drr_pct']==8
 assert all(a[k]is False for k in('advertising_writes','stock_writes','funding_writes','telegram_notifications'))
 def authority():assert cache.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(cache,WB())
 old=cache.get(ROOT+':execution')
 if old:
  if old['status']=='verified':print('Already verified; no replay');return
  raise ValueError('Existing price journal must be inspected, no blind replay')
 e=dict(status='preflight',approval_key=ROOT+':approval',created_at=stamp(),wb_writes=0,telegram_calls=0,stock_writes=0,funding_writes=0,advertising_writes=0,model_calls=0)
 assert cache.create(ROOT+':execution',e)
 def save():cache.put(ROOT+':execution',json.loads(json.dumps(e)))
 expected={i['nm_id']:dict(nmID=i['nm_id'],price=i['base_target'],discount=i['discount'])for i in p['items']};original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json');path=u.path
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='api.moysklad.ru':
   ok=m=='GET'and path.startswith('/api/remap/1.2/');time.sleep(.4)
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and path=='/api/v3/stocks/2126188'
  elif u.hostname=='discounts-prices-api.wildberries.ru':
   ok=m=='GET'and path in('/ping','/api/v2/list/goods/filter','/api/v2/history/tasks','/api/v2/history/goods/task')
   if m=='POST':
    ok=path=='/api/v2/upload/task'and isinstance(b,dict)and set(b)=={'data'}and 1<=len(b['data'])<=6 and len({x['nmID']for x in b['data']})==len(b['data'])and all(expected.get(x['nmID'])==x for x in b['data'])
    assert ok,'Outside six exact approved seller prices';authority();assert not e.get('submitted_at'),'No repeated upload';e['submitted_at']=stamp();e['submitted_body']=b;save()
  else:ok=False
  assert ok,'Outside exact owner price scope '+m+' '+str(u.hostname)+path
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 class OwnerIO(AdvertisingIO):
  def validate(self,approval):
   authority();assert approval['owner_approval_key']==ROOT+':approval'and approval['selections']==self.selections
  def tg(self,*args,**kwargs):raise RuntimeError('Telegram prohibited')
  def prices(self,ids):
   wanted={str(n)for n in ids};found={}
   for offset in range(0,3000,1000):
    rows=self.wb('/api/v2/list/goods/filter?limit=1000&offset='+str(offset)).get('listGoods');assert isinstance(rows,list)
    for row in rows:
     if str(row['nmID'])in wanted:
      assert str(row['nmID'])not in found;found[str(row['nmID'])]=row
    if len(rows)<1000:break
   assert set(found)==wanted,'Exact price coverage incomplete';return found
 io=OwnerIO()
 try:
  io.capability();goods=io.prices(sorted(IDS));e['before']=goods;save();selections=[]
  for i in p['items']:
   g=goods[str(i['nm_id'])];assert Decimal(i['target_cny'])>=Decimal(i['current_cny'])*Decimal('.95')
   assert g['discount']==i['discount']and g.get('clubDiscount')==0
   s=dict(nm_id=str(i['nm_id']),article=i['article'],current_cny=i['current_cny'],target_cny=i['target_cny'],base_cny=str(i['base_before']),seller_discount=i['discount'],club_discount=g['clubDiscount'],action='Снижение')
   request=plan(s,g);assert request is None or request==expected[i['nm_id']];selections.append(s)
  io.selections=selections
  stock=Reader().stock([i['article']for i in p['items']],'msk');assert stock['coverage_complete']and stock['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
  source=cache.get('china_agent:advertising_full_growth:2026-11-25:v1:inputs:midday');assert source['status']=='complete'and source['cabinet']=='token_3'and(datetime.now(timezone.utc)-datetime.fromisoformat(source['observed_at'])).total_seconds()<8*3600
  prices=dict(observed_at=stamp(),rows=[dict(nm_id=i['nm_id'],article=i['article'],seller_price=float(i['target_cny']))for i in p['items']]);inputs=dict(products=source['own'],prices=prices,stock=stock,fx=source['fx'])
  econ=model_rows(inputs,cache.get('china_agent:new_ad_economics_policy:v1'),cache.get('china_agent:expected_profit_delivery_model:v1'));assert not econ['missing']
  for nm in IDS:
   row=econ['rows'][str(nm)];assert row['stock_free']>0 and row['expected_margin_before_ads_cny']-.08*row['seller_price_cny']>0 and not row['buyout_fallback']
  # Read-only published availability against exact current price size IDs.
  normalized=dict(rows=[dict(nm_id=int(nm),size_ids=[s['sizeID']for s in g['sizes']])for nm,g in goods.items()]);pub=published_stock(io,normalized,sorted(IDS));assert not pub['missing_nm_ids']and all(pub['amounts'][str(n)]>0 for n in IDS)
  e.update(preflight_stock=stock,target_economics=econ,published=pub,baseline=p['baseline_key'],baseline_observed_at=stamp());save()
  key=PREFIX+'-1004342917488:0:5122667182:'+digest(selections);approval=dict(schema_version=2,execution_authorized=True,execution_policy=POLICY,approval_policy='all_current_human_group_members',decision='approved_recommendation',chat_id=-1004342917488,bot_id=8780468043,report_job_id=0,report_date=day(),actor_user_id=5122667182,created_at=stamp(),selections=selections,owner_approval_key=ROOT+':approval',basis='explicit_owner_emergency_six_price_tests',telegram_notifications=False)
  assert io.create(key,approval),'Price approval already exists; inspect without replay';e.update(status='running',price_approval_key=key,price_execution_key='china_agent:price_execution:v1:'+key[len(PREFIX):]);save()
  pe=process(io,key,polls=12);e.update(price_result=pe,wb_writes=int(bool(pe.get('upload_id'))));save()
  assert pe['status']=='done'and len(pe['items'])==6 and all(x['status']in('applied','already_at_target')for x in pe['items']),'WB readback not complete; no replay'
  after=io.prices(sorted(IDS))
  for i in p['items']:
   g=after[str(i['nm_id'])];assert g['discount']==i['discount']and g['clubDiscount']==0 and g['currencyIsoCode4217']=='CNY'and g['vendorCode']==i['article']
   assert all(Decimal(str(s['price']))==Decimal(i['base_target'])and Decimal(str(s['discountedPrice']))==Decimal(i['target_cny'])for s in g['sizes'])
  at=stamp();changed=datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=3))).date();first=str(changed+timedelta(days=1));early=str(changed+timedelta(days=2));normal=str(changed+timedelta(days=4))
  snap=io.get('china_agent:prices:v1')or{};merged={str(g['nmID']):g for g in snap.get('rows',[])};merged.update(after);snap.update(rows=list(merged.values()),cabinet='token_3',observed_at=at,source='owner_remaining25_six_verified_readback',execution_key=e['price_execution_key']);io.put('china_agent:prices:v1',snap)
  from china_experiment_journal import receipt_changes
  for i in p['items']:
   nm=str(i['nm_id']);receipt=dict(status='verified',kind='price_change',cabinet='token_3',before=goods[nm],after=after[nm],submitted_at=e.get('submitted_at',at),verified_at=at,approval_key=ROOT+':approval',price_execution_key=e['price_execution_key'],telegram_allowed=False);rk=ROOT+':item:'+nm;assert io.create(rk,receipt);assert receipt_changes(rk,receipt)
   event=dict(status='verified',record_type='verified_action',event_id='owner-remaining25-price-'+nm,source_key=rk,started_at=e.get('submitted_at',at),verified_at=at,action=dict(kind='price_change',nm_ids=[i['nm_id']],article=i['article'],before=i['current_cny'],after=i['target_cny'],currency='CNY'),evaluation=dict(first_full_day=first,early_review=early,normal_review=normal,normal_completed_days=3),grants_action_permission=False,telegram_allowed=False);assert io.create('china_agent:experience:v1:owner-remaining25-price-'+nm,event)
  tracking=dict(status='active',execution_key=e['price_execution_key'],canonical_execution_key=ROOT+':execution',items=p['items'],baseline_key=p['baseline_key'],target_economics=econ,first_complete_msk_day=first,first_early_review_msk_day=early,normal_review_msk_day=normal,normal_completed_days=3,existing_hourly_collection=True,new_monitor=False,auto_revert_authorized=False,auto_changes=False,target_drr_pct=8)
  assert io.create(ROOT+':tracking',tracking);e.update(status='verified',after=after,verified_at=at,reporting_registered=True,first_complete_msk_day=first,first_early_review_msk_day=early,normal_review_msk_day=normal);save()
 except Exception as ex:
  state=e.get('price_result',{}).get('status');e.update(status='uncertain'if state in('submitting','submitted','uncertain')else'needs_readback'if e.get('submitted_at')or e.get('wb_writes')else'blocked',reason=type(ex).__name__+': '+str(ex)[:240]);save();raise
 finally:requests.sessions.Session.request=original
 print(json.dumps(dict(status=e['status'],items=6,upload_id=e['price_result'].get('upload_id'),wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()

