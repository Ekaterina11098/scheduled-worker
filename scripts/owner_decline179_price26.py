"""Owner-approved 5% reduction for exact declined conversion cohort; no TG/ads/funding."""
import os,json,time,hashlib,requests
from datetime import datetime,timezone,timedelta
from decimal import Decimal,ROUND_CEILING
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from china_price_apply import process,PREFIX,POLICY,day,plan
from china_moysklad_read import Reader
from china_morning_readiness import published_stock
ROOT='china_agent:owner_decline179_price26:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def main():
 cache=Cache();a=cache.get(ROOT+':approval');intent=cache.get(ROOT+':intent')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['intent_sha256']==digest(intent)
 assert len(intent['items'])==179 and len({i['nm_id']for i in intent['items']})==179 and intent['reduction_pct']==5
 assert all(a[k]is False for k in ('advertising_writes','stock_writes','funding_writes','telegram_notifications'))
 def authority():assert cache.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(cache,WB())
 if cache.get(ROOT+':execution'):raise ValueError('Existing journal: inspect, no repeat')
 e=dict(status='preflight',created_at=stamp(),wb_writes=0,telegram_calls=0,advertising_writes=0,stock_writes=0,funding_writes=0,model_calls=0,skipped=[],batch_results=[]);assert cache.create(ROOT+':execution',e)
 def save():cache.put(ROOT+':execution',json.loads(json.dumps(e)))
 expected={};original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();path=u.path;b=kw.get('json')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and path.startswith('/api/remap/1.2/');time.sleep(.4)
  elif u.hostname=='marketplace-api.wildberries.ru':ok=m=='POST'and path=='/api/v3/stocks/2126188'
  elif u.hostname=='discounts-prices-api.wildberries.ru':
   ok=m=='GET'and path in('/ping','/api/v2/list/goods/filter','/api/v2/history/tasks','/api/v2/history/goods/task')
   if m=='POST':
    ok=path=='/api/v2/upload/task'and isinstance(b,dict)and set(b)=={'data'}and 1<=len(b['data'])<=100 and len({x['nmID']for x in b['data']})==len(b['data'])and all(expected.get(x['nmID'])==x for x in b['data'])
    assert ok,'Outside approved exact reductions';authority();used={z['nmID']for old in e.get('submitted_bodies',[])for z in old['data']};assert not used.intersection(z['nmID']for z in b['data']),'Repeated upload blocked';e['submitted_at']=stamp();e.setdefault('submitted_bodies',[]).append(b);save()
  else:ok=False
  assert ok,'Outside owner price scope '+m+' '+str(u.hostname)+path
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 class OwnerIO(AdvertisingIO):
  def validate(self,approval):authority();assert approval['owner_approval_key']==ROOT+':approval'and approval['selections']==self.selections
  def tg(self,*args,**kwargs):raise RuntimeError('Telegram prohibited')
  def prices(self,ids):
   wanted={str(n)for n in ids};found={}
   for offset in range(0,3000,1000):
    rows=self.wb('/api/v2/list/goods/filter?limit=1000&offset='+str(offset)).get('listGoods');assert isinstance(rows,list)
    for row in rows:
     if str(row['nmID'])in wanted:assert str(row['nmID'])not in found;found[str(row['nmID'])]=row
    if len(rows)<1000:break
   return found
 io=OwnerIO()
 try:
  io.capability();ids=[i['nm_id']for i in intent['items']];goods=io.prices(ids);e['before']=goods;save()
  prior=cache.get('china_agent:owner_catalog25_actions26:v2')or{};stock=prior.get('stock',{});sm={r['article']:r for r in stock.get('rows',[])};e['stock_reference_only']=stock;e['stock_not_eligibility_filter']=True;save();selections=[];proposal=[]
  for i in intent['items']:
   n=str(i['nm_id']);g=goods.get(n);st=sm.get(i['article']);reason=None
   if not g:reason='WB_price_missing'
   elif g.get('vendorCode')!=i['article']or g.get('currencyIsoCode4217')!='CNY'or g.get('editableSizePrice')is not False:reason='WB_identity_currency_or_size_mode'
   elif len({str(z['price'])for z in g['sizes']})!=1 or len({str(z['discountedPrice'])for z in g['sizes']})!=1:reason='ambiguous_size_prices'
   if reason:e['skipped'].append(dict(**i,reason=reason));continue
   old=Decimal(str(g['sizes'][0]['discountedPrice']));discount=g['discount'];assert type(discount)is int and 0<=discount<100
   factor=Decimal(100-discount)/100;base=(old*Decimal('.95')/factor).to_integral_value(rounding=ROUND_CEILING);target=base*factor
   assert old*Decimal('.95')<=target<old,'Invalid reduction'
   s=dict(nm_id=n,article=i['article'],current_cny=str(old),target_cny=str(target),base_cny=str(g['sizes'][0]['price']),seller_discount=discount,club_discount=g.get('clubDiscount'),action='Снижение')
   request=plan(s,g);assert request==dict(nmID=int(n),price=int(base),discount=discount);expected[int(n)]=request;selections.append(s);proposal.append(dict(**s,actual_reduction_pct=float((1-target/old)*100)))
  assert len(selections)+len(e['skipped'])==179;e.update(items=proposal,status='prepared');save();assert cache.create(ROOT+':proposal',dict(items=proposal,skipped=e['skipped'],basis=intent,prepared_at=stamp()))
  verified=[];execution_by_nm={};submitted_by_nm={}
  for offset in range(0,len(selections),100):
   batch=selections[offset:offset+100];io.selections=batch;key=PREFIX+'-1004342917488:0:5122667182:'+digest(batch);ek='china_agent:price_execution:v1:'+key[len(PREFIX):]
   approval=dict(schema_version=2,execution_authorized=True,execution_policy=POLICY,approval_policy='all_current_human_group_members',decision='approved_recommendation',chat_id=-1004342917488,bot_id=8780468043,report_job_id=0,report_date=day(),actor_user_id=5122667182,created_at=stamp(),selections=batch,owner_approval_key=ROOT+':approval',basis='explicit_owner_declined179_five_percent',telegram_notifications=False)
   assert io.create(key,approval),'Existing batch: no blind replay';e.update(status='running',active_execution_key=ek);save();result=process(io,key,polls=12);e['batch_results'].append(dict(execution_key=ek,result=result));e['wb_writes']=sum(bool(x['result'].get('upload_id'))for x in e['batch_results']);save()
   assert result['status']=='done','Uncertain batch; no continuation'
   for x in result['items']:
    n=x['selection']['nm_id']
    if x['status']in('applied','already_at_target'):verified.append(x);execution_by_nm[n]=ek;submitted_by_nm[n]=result.get('created_at',stamp())
    elif x['status']=='blocked':e['skipped'].append(dict(nm_id=int(n),article=x['selection']['article'],reason=x.get('reason','blocked')))
    else:raise ValueError('WB item not verified; no continuation')
  after=io.prices([int(x['selection']['nm_id'])for x in verified]);at=stamp();changed=datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=3))).date();first=str(changed+timedelta(days=1));early=str(changed+timedelta(days=2));normal=str(changed+timedelta(days=4))
  from china_experiment_journal import receipt_changes
  for x in verified:
   s=x['selection'];n=s['nm_id'];g=after[n];assert g['discount']==s['seller_discount']and g.get('clubDiscount')==s['club_discount']and g['currencyIsoCode4217']=='CNY'and g['vendorCode']==s['article'];assert all(Decimal(str(z['discountedPrice']))==Decimal(s['target_cny'])and Decimal(str(z['price']))==Decimal(expected[int(n)]['price'])for z in g['sizes'])
   rk=ROOT+':item:'+n;receipt=dict(status='verified',kind='price_change',cabinet='token_3',before=goods[n],after=g,submitted_at=submitted_by_nm[n],verified_at=at,approval_key=ROOT+':approval',price_execution_key=execution_by_nm[n],canonical_execution_key=ROOT+':execution',telegram_allowed=False);assert io.create(rk,receipt);assert receipt_changes(rk,receipt)
   event=dict(status='verified',record_type='verified_action',event_id='owner-decline179-price26-'+n,source_key=rk,started_at=submitted_by_nm[n],verified_at=at,action=dict(kind='price_change',nm_ids=[int(n)],article=s['article'],before=s['current_cny'],after=s['target_cny'],currency='CNY'),evaluation=dict(first_full_day=first,early_review=early,normal_review=normal,normal_completed_days=3),grants_action_permission=False,telegram_allowed=False);assert io.create('china_agent:experience:v1:owner-decline179-price26-'+n,event)
  snap=io.get('china_agent:prices:v1')or{};merged={str(g['nmID']):g for g in snap.get('rows',[])};merged.update(after);snap.update(rows=list(merged.values()),cabinet='token_3',observed_at=at,source='owner_decline179_price26_verified',execution_key=ROOT+':execution');io.put('china_agent:prices:v1',snap)
  tracking=dict(status='active',canonical_execution_key=ROOT+':execution',items=[x['selection']for x in verified],baseline_key='china_agent:wb_evidence:v1:funnel:2026-11-25:2026-11-25',first_complete_msk_day=first,first_early_review_msk_day=early,normal_review_msk_day=normal,normal_completed_days=3,existing_hourly_collection=True,new_monitor=False,auto_changes=False,auto_revert_authorized=False,owner_price_override=True);assert io.create(ROOT+':tracking',tracking)
  assert len(verified)+len(e['skipped'])==179;e.update(status='verified',verified_items=verified,after=after,verified_at=at,reporting_registered=True,first_complete_msk_day=first,first_early_review_msk_day=early,normal_review_msk_day=normal);save();print(json.dumps(dict(status='verified',changed=len(verified),skipped=len(e['skipped']),wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:
  e.update(status='needs_readback'if e.get('submitted_at')else'blocked',reason=type(ex).__name__+': '+str(ex)[:240]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

