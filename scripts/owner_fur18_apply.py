"""Exact owner-approved two fur price tests; no advertising, funding, stock or TG writes."""
import os,json,hashlib,copy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_price_apply import IO,process,PREFIX,POLICY,day,plan
from china_moysklad_read import Reader
from china_advertising_economic_review import model_rows

ROOT='china_agent:owner_fur_price_test:2026-11-18:v1'
IDS={2216111729,2216167898}
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def main():
 c=Cache();a=c.get(ROOT+':approval');p=c.get(ROOT+':proposal')
 assert a['status']=='approved' and a['owner_id']==5122667182 and a['proposal_sha256']==digest(p)
 assert {i['nm_id']for i in p['items']}==IDS and len(p['items'])==2
 assert a['advertising_writes'] is False and a['stock_writes'] is False and a['funding_writes'] is False and a['telegram_notifications'] is False
 def authority():
  assert c.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(c,WB())
 e=dict(status='preflight',approval_key=ROOT+':approval',created_at=stamp(),wb_writes=0,telegram_calls=0,stock_writes=0,funding_writes=0,advertising_writes=0,model_calls=0)
 assert c.create(ROOT+':execution',e),'Prior execution exists; inspect readback, never replay'
 def save():c.put(ROOT+':execution',e)
 expected={i['nm_id']:dict(nmID=i['nm_id'],price=i['base_target'],discount=i['discount'])for i in p['items']}
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json');path=u.path
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=path.startswith('/rest/v1/') and m in('GET','POST','PATCH')
  elif u.hostname=='api.moysklad.ru':ok=m=='GET' and path.startswith('/api/remap/1.2/')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET' and path in('/api/advert/v2/adverts','/api/advert/v1/config')
  elif u.hostname=='discounts-prices-api.wildberries.ru':
   ok=m=='GET' and path in('/ping','/api/v2/list/goods/filter','/api/v2/history/tasks','/api/v2/history/goods/task')
   if m=='POST':
    ok=path=='/api/v2/upload/task' and isinstance(b,dict) and set(b)=={'data'} and 1<=len(b['data'])<=2 and len({x['nmID']for x in b['data']})==len(b['data']) and all(expected.get(x['nmID'])==x for x in b['data'])
  else:ok=False
  assert ok,'Outside exact price test authority: '+m+' '+str(u.hostname)+path
  if m=='POST' and u.hostname=='discounts-prices-api.wildberries.ru':
   authority();assert not e.get('submitted_at'),'No duplicate upload';e['submitted_at']=stamp();save()
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 class OwnerIO(IO):
  def validate(self,approval):
   authority();assert approval['owner_approval_key']==ROOT+':approval' and approval['selections']==self.selections
  def tg(self,*args,**kwargs):raise RuntimeError('Telegram prohibited')
 io=OwnerIO()
 try:
  io.capability();goods=io.prices([str(n)for n in sorted(IDS)]);e['before']=goods;save()
  selections=[]
  for i in p['items']:
   g=goods[str(i['nm_id'])]
   assert Decimal(str(i['target_cny']))>=Decimal(str(i['current_cny']))*Decimal('.95')
   s=dict(nm_id=str(i['nm_id']),article=i['article'],current_cny=i['current_cny'],target_cny=i['target_cny'],base_cny=str(i['base_before']),seller_discount=i['discount'],club_discount=0,action='Снижение')
   req=plan(s,g);assert req is None or req==expected[i['nm_id']]
   assert g['discount']==i['discount'] and g.get('clubDiscount')==0
   selections.append(s)
  io.selections=selections
  stock=Reader().stock([i['article']for i in p['items']],'msk')
  assert stock['coverage_complete'] and stock['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
  approved=c.get('china_agent:owner_fur18_ready:v1:plan');assert approved['status']=='ready_proposal_not_executed'
  econ=dict(status='available',rows={},basis='approved_plan_rechecked_current_MSK_cost',preliminary=True,own_completed_sample=0)
  rows={r['article']:r for r in stock['rows']};fx=approved['economics']['fx_rub_cny']
  for i in p['items']:
   st=rows[i['article']];cost=st['price']/100;free=st['stock']-st['reserve']
   assert free>0 and abs(cost-1307.11)<.02
   margin=.3*(404*.72-cost/fx)-38;stress=.25*(404*.72-cost/fx)-38
   assert margin>0 and stress>0
   econ['rows'][str(i['nm_id'])]=dict(seller_price_cny=404,own_cogs_rub=cost,stock_free=free,buyout=.3,buyout_fallback=True,stress_buyout=.25,expected_margin_before_ads_cny=margin,stress_margin_before_ads_cny=stress,unknown_reverse_and_shared_costs=True,fx_rub_per_cny=fx,commission_pct=20,tax_pct=5,payment_reserve_pct=3,logistics_cny=38,preliminary=True,source_key='china_agent:owner_fur18_ready:v1:plan')
  e.update(preflight_stock=stock,target_economics=econ,baseline=p['baseline'],baseline_observed_at=stamp());save()
  ak=PREFIX+'-1004342917488:0:5122667182:'+digest(selections)
  pa=dict(schema_version=2,execution_authorized=True,execution_policy=POLICY,approval_policy='all_current_human_group_members',decision='approved_recommendation',chat_id=-1004342917488,bot_id=8780468043,report_job_id=0,report_date=day(),actor_user_id=5122667182,created_at=stamp(),selections=selections,owner_approval_key=ROOT+':approval',basis='explicit_codex_fur_price_two_tests')
  old=io.get(ak)
  if old:raise AssertionError('Price approval already exists: inspect execution, do not replay')
  assert io.create(ak,pa)
  e.update(status='running',price_approval_key=ak,price_execution_key='china_agent:price_execution:v1:'+ak[len(PREFIX):]);save()
  pe=process(io,ak,polls=12);e.update(price_result=pe,wb_writes=int(bool(pe.get('upload_id'))));save()
  assert pe['status']=='done' and len(pe['items'])==2 and all(x['status']in('applied','already_at_target')for x in pe['items']),'Price readback incomplete; no automatic replay'
  after=io.prices([str(n)for n in sorted(IDS)])
  for i in p['items']:
   g=after[str(i['nm_id'])];assert g['discount']==i['discount'] and g['clubDiscount']==0 and g['currencyIsoCode4217']=='CNY'
   assert all(Decimal(str(s['price']))==Decimal(i['base_target']) and Decimal(str(s['discountedPrice']))==Decimal(i['target_cny'])for s in g['sizes'])
  verified=stamp();changed=datetime.fromisoformat(verified).astimezone(timezone(timedelta(hours=3))).date()
  e.update(status='verified',after=after,verified_at=verified,first_complete_msk_day=str(changed+timedelta(days=1)),first_early_review_msk_day=str(changed+timedelta(days=2)),normal_review_msk_day=str(changed+timedelta(days=4)),auto_revert_authorized=False)
  snap=c.get('china_agent:prices:v1')or{};merged={str(g['nmID']):g for g in snap.get('rows',[])};merged.update(after)
  snap.update(rows=list(merged.values()),cabinet='token_3',observed_at=verified,source='owner_fur_price18_verified_readback',execution_key=e['price_execution_key']);c.put('china_agent:prices:v1',snap)
  tracking=dict(status='active',execution_key=e['price_execution_key'],canonical_execution_key=ROOT+':execution',verified_at=verified,items=p['items'],baseline=p['baseline'],target_economics=econ,first_complete_msk_day=e['first_complete_msk_day'],first_early_review_msk_day=e['first_early_review_msk_day'],normal_review_msk_day=e['normal_review_msk_day'],metrics=['open_card_count','add_to_cart_count','funnel_orders_count','orders_count','orders_sum','buyer_price_spp','availability','ad_spend'],compare_periods=[['2026-11-15','2026-11-17']],baseline_general_funnel='unavailable; must not replace by advertising clicks/carts',grants_action_permission=False,monitor_created=False,auto_revert_authorized=False)
  assert c.create(ROOT+':tracking',tracking)
  from china_experiment_journal import receipt_changes
  for i in p['items']:
   nm=str(i['nm_id']);receipt=dict(status='verified',kind='price_change',cabinet='token_3',before=goods[nm],after=after[nm],submitted_at=e.get('submitted_at',verified),verified_at=verified,approval_key=ROOT+':approval',price_execution_key=e['price_execution_key'],telegram_allowed=False)
   rk=ROOT+':item:'+nm;assert c.create(rk,receipt)
   assert receipt_changes(rk,receipt), 'Standard experiment reader did not recognize the price change'
   event=dict(record_type='verified_action',event_id='owner-fur-price18-'+nm,source_key=rk,started_at=receipt['submitted_at'],verified_at=verified,action=dict(kind='price_change',nm_ids=[i['nm_id']],article=i['article'],before=425,after=404,currency='CNY'),evaluation=dict(first_full_day=e['first_complete_msk_day'],early_review=e['first_early_review_msk_day'],normal_review=e['normal_review_msk_day'],normal_completed_days=3),grants_action_permission=False,telegram_allowed=False)
   assert c.create('china_agent:experience:v1:owner-fur-price18-'+nm,event)
  e['reporting_registered']=True;save()
 except Exception as ex:
  prior=e.get('price_result',{}).get('status');e.update(status='uncertain'if prior in('submitting','submitted','uncertain')else'needs_readback'if e.get('wb_writes')else'blocked',reason=type(ex).__name__+': '+str(ex)[:220]);save();raise
 finally:requests.sessions.Session.request=original
 print(json.dumps(dict(status=e['status'],upload_id=e['price_result'].get('upload_id'),items=2,wb_writes=e['wb_writes'],telegram_calls=0)))
if __name__=='__main__':main()

