"""Eight exact Codex-approved actions. No stock/funding/TG/model writes."""
import os,json,time,copy,hashlib
from datetime import datetime,timezone
from urllib.parse import urlparse
from decimal import Decimal
import requests
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_new_ads import Transport
from china_price_apply import IO,process,PREFIX,POLICY,sha,day,plan
from china_moysklad_read import Reader
ROOT='china_agent:owner_growth_audit:2026-11-17:v1'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def scope(p):
 return dict(advertising=[{k:i[k]for k in('id','kind','campaign_id','nm_id','placement','old_minor','target_minor')if k in i}for i in p['advertising']],prices=[{k:i[k]for k in('id','nm_id','base_price_before','base_price_target','discount_before','discount_target')}for i in p['prices']])
def main():
 c=Cache();w=WB();a=c.get(ROOT+':approval');p=c.get(ROOT+':proposal')
 assert a['status']=='approved' and a['owner_id']==5122667182 and a['proposal_sha256']==digest(scope(p))
 assert a['stock_writes']is False and a['funding_writes']is False and a['telegram_notifications']is False
 assert a['approved_ids']==[i['id']for i in p['advertising']+p['prices']]
 def authority():
  assert c.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(c,w)
 e=dict(status='preflight',approval_key=ROOT+':approval',items=[],wb_writes=0,stock_writes=0,funding_writes=0,telegram_calls=0,model_calls=0,created_at=stamp())
 assert c.create(ROOT+':execution',e),'Prior execution exists; inspect, never replay'
 def save():c.put(ROOT+':execution',e)
 allowed_bid=[dict(bids=[dict(advert_id=i['campaign_id'],nm_bids=[dict(nm_id=i['nm_id'],bid_kopecks=i['target_minor'],placement=i['placement'])])])for i in p['advertising']if i['kind']=='ad_set_bid']
 allowed_ex=[dict(nms=[dict(advert_id=i['campaign_id'],nms=dict(add=[],delete=[i['nm_id']]))])for i in p['advertising']if i['kind']=='ad_exclude_sku']
 wanted_prices={i['nm_id']:dict(nmID=i['nm_id'],price=i['base_price_target'],discount=i['discount_target'])for i in p['prices']}
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();b=kw.get('json');path=u.path
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='api.moysklad.ru':ok=m=='GET'and path.startswith('/api/remap/1.2/')
  elif u.hostname=='advert-api.wildberries.ru':
   ok=(m=='GET'and path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v3/fullstats'))or(m=='POST'and path=='/api/advert/v1/bids/min')
   if m=='PATCH':ok=(path=='/api/advert/v1/bids'and b in allowed_bid)or(path=='/adv/v0/auction/nms'and b in allowed_ex)
  elif u.hostname=='discounts-prices-api.wildberries.ru':
   ok=m=='GET'and path in('/ping','/api/v2/list/goods/filter','/api/v2/history/tasks','/api/v2/history/goods/task')
   if m=='POST':ok=path=='/api/v2/upload/task'and isinstance(b,dict)and set(b)=={'data'}and 0<len(b['data'])<=2 and len({v['nmID']for v in b['data']})==len(b['data'])and all(wanted_prices.get(v['nmID'])==v for v in b['data'])
  else:ok=False
  assert ok,'Outside exact owner scope: '+m+' '+str(u.hostname)+path
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 io=type('AdIO',(),dict(token=w.token))();t=Transport(io)
 class PriceIO(IO):
  def validate(self,approval):
   authority();assert approval['owner_approval_key']==ROOT+':approval'and approval['selections']==self.selections
   validate_identity(c,w)
  def tg(self,*args,**kw):raise RuntimeError('Telegram prohibited')
 pr=PriceIO()
 try:
  cfg=t.config();assert cfg['currency']=='CNY'and cfg['cpcStep']==1
  ids=sorted({i['campaign_id']for i in p['advertising']});campaigns=w.campaigns(ids)
  price_ids=sorted({i['nm_id']for i in p['advertising']+p['prices']});goods=pr.prices(list(map(str,price_ids)))
  e['preflight_campaigns']=campaigns;e['preflight_prices']=goods
  fresh=c.get(ROOT+':fresh');assert fresh['status']=='complete'and(datetime.now(timezone.utc)-datetime.fromisoformat(fresh['completed_at'])).total_seconds()<7200
  for i in p['advertising']:
   camp=campaigns[str(i['campaign_id'])];assert camp['status']==9 and camp['currency']=='CNY'and camp['settings']['payment_type']=='cpc'
   assert camp['settings']['placements']==dict(search=i['placement']=='search',recommendations=i['placement']=='recommendations')
   n=next((n for n in camp['nm_settings']if n['nm_id']==i['nm_id']),None)
   if n is None:assert i['kind']=='ad_exclude_sku';continue
   assert n['bids_kopecks'][i['placement']]in({i['old_minor'],i['target_minor']}if i['kind']=='ad_set_bid'else{i['old_minor']})
   g=goods[str(i['nm_id'])];assert g['vendorCode']==i['article']and g['currencyIsoCode4217']=='CNY'
   assert all(Decimal(str(s['discountedPrice']))==Decimal(str(i['economics']['seller_price_cny']))for s in g['sizes'])
   if i['kind']=='ad_set_bid':assert w.minimums(i['campaign_id'],[i['nm_id']],i['placement'])[i['nm_id']]<=i['target_minor']<=cfg['cpcMaxBid']
  # Exact two seller-base changes through the existing durable price engine.
  selections=[]
  for i in p['prices']:
   g=goods[str(i['nm_id'])]
   s=dict(nm_id=str(i['nm_id']),article=i['article'],current_cny=str(i['current_cny']),target_cny=str(i['target_cny']),base_cny=str(i['base_price_before']),seller_discount=i['discount_before'],club_discount=g.get('clubDiscount'),action='Снижение')
   req=plan(s,g);assert req is None or req==wanted_prices[i['nm_id']];selections.append(s)
  pr.selections=selections;pr.capability()
  keep=[i for i in p['advertising']if i['kind']=='ad_set_bid'and i['target_minor']>i['old_minor']]+p['prices']
  stock=Reader().stock([i['article']for i in keep],'msk')
  assert stock['coverage_complete']and stock['warehouse_id']=='3c67619d-f25d-11ee-0a80-0c6f000a027a'
  for i in keep:
   match=[r for r in stock['rows']if str(r.get('article','')).casefold()==i['article'].casefold()];assert len(match)==1 and match[0]['stock']-match[0]['reserve']>0
  e['preflight_stock']=stock
  e['baseline_fullstats']=w.req('/adv/v3/fullstats?ids='+','.join(map(str,ids))+'&beginDate=2026-11-17&endDate=2026-11-17');e['baseline_observed_at']=stamp();save()
  def proj(camp):return {k:camp[k]for k in('id','status','currency','bid_type','settings','nm_settings')}
  def register(cid,before,after,item):
   key=ROOT+':action:'+digest(item['id'])[:16]
   rec=dict(status='verified',before=before,after=after,items=[dict(item,status='verified')],verified_at=stamp(),authorization_key=ROOT+':approval',parent=ROOT+':execution',baseline_observed_at=e['baseline_observed_at'],baseline_fullstats=[x for x in e['baseline_fullstats']if x['advertId']==cid])
   c.put(key,rec);registry=c.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=key;c.put('china_agent:verified_campaign_state:v1',registry)
   alias='china_agent:ad_rule_execution:owner-growth17-'+digest(item['id'])[:16]+':v1'
   c.put(alias,dict(status='done',canonical_source_execution_key=key,alias_of_verified_batch=True,wb_writes=0,items=[dict(item,status='verified',before=before,after=after,verified_at=rec['verified_at'],source_execution_key=key)]))
   return key
  e['status']='running';save()
  for item in p['advertising']:
   authority();cid=item['campaign_id'];before=w.campaigns([cid])[str(cid)];expected=copy.deepcopy(before)
   n=next((n for n in before['nm_settings']if n['nm_id']==item['nm_id']),None)
   s=dict(id=item['id'],kind=item['kind'],campaign_id=cid,nm_id=item['nm_id'],article=item['article'],before=before,status='preflight');e['items'].append(s);save()
   if (item['kind']=='ad_exclude_sku'and n is None)or(item['kind']=='ad_set_bid'and n and n['bids_kopecks'][item['placement']]==item['target_minor']):
    s.update(status='already_at_target',after=before,verified_at=stamp());save();continue
   assert before['status']==9 and before['settings']==campaigns[str(cid)]['settings']and n and n['bids_kopecks'][item['placement']]==item['old_minor']
   if item['kind']=='ad_set_bid':
    next(n for n in expected['nm_settings']if n['nm_id']==item['nm_id'])['bids_kopecks'][item['placement']]=item['target_minor']
    path='/api/advert/v1/bids';body=dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=item['nm_id'],bid_kopecks=item['target_minor'],placement=item['placement'])])])
   else:
    expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']!=item['nm_id']]
    path='/adv/v0/auction/nms';body=dict(nms=[dict(advert_id=cid,nms=dict(add=[],delete=[item['nm_id']]))])
   assert proj(w.campaigns([cid])[str(cid)])==proj(before)
   s.update(status='submitting',request=body,submitted_at=stamp());save()
   try:s['response']=w.req(path,'PATCH',body,write=True)
   except Exception:s['status']='uncertain';save();raise
   e['wb_writes']+=1;s['status']='accepted';save()
   for attempt in range(10):
    after=w.campaigns([cid])[str(cid)]
    if proj(after)==proj(expected):break
    if attempt==9:s.update(status='uncertain',after=after);save();raise RuntimeError('Ad readback unresolved; no retry')
    time.sleep(7)
   s.update(status='verified',after=after,verified_at=stamp());s['receipt_key']=register(cid,before,after,item);save()
  ak=PREFIX+'-1004342917488:0:5122667182:'+digest(selections)
  pa=dict(schema_version=2,execution_authorized=True,execution_policy=POLICY,approval_policy='all_current_human_group_members',decision='approved_recommendation',chat_id=-1004342917488,bot_id=8780468043,report_job_id=0,report_date=day(),actor_user_id=5122667182,created_at=stamp(),selections=selections,owner_approval_key=ROOT+':approval',basis='explicit_codex_exact_growth_plan')
  assert pr.create(ak,pa),'Existing price approval; inspect'
  e['price_approval_key']=ak;e['price_execution_key']='china_agent:price_execution:v1:'+ak[len(PREFIX):];save()
  pe=process(pr,ak,polls=12)
  e['price_result']=pe;e['wb_writes']+=int(bool(pe.get('upload_id')))
  assert pe['status']=='done'and len(pe['items'])==2 and all(i['status']in('applied','already_at_target')for i in pe['items']),'Prices not yet WB verified'
  snapshot=c.get('china_agent:prices:v1')or{}
  merged={str(g['nmID']):g for g in snapshot.get('rows',[])}
  for i in pe['items']:
   if i.get('readback'):merged[str(i['readback']['nmID'])]=i['readback']
  snapshot.update(cabinet='token_3',observed_at=stamp(),rows=list(merged.values()),source='owner_growth17_verified_readback',execution_key=e['price_execution_key']);c.put('china_agent:prices:v1',snapshot)
  tracking=c.get('china_agent:bid_raise_tracking:v1')or dict(items={})
  for i,s in zip(p['advertising'],e['items']):
   if i['kind']=='ad_set_bid'and s['status']=='verified':tracking.setdefault('items',{})[str(i['campaign_id'])+':'+str(i['nm_id'])]=dict(status='active',plan=i,started_at=s['submitted_at'],verified_at=s['verified_at'],execution_key=s['receipt_key'],target_drr_pct=5,first_complete_msk_day='2026-11-18',first_early_review_msk_day='2026-11-19',auto_revert_authorized=False)
  c.put('china_agent:bid_raise_tracking:v1',tracking)
  e.update(status='verified',verified_at=stamp(),first_complete_msk_day='2026-11-18',first_early_review_msk_day='2026-11-19',price_normal_review_msk_day='2026-11-21',reporting_registered=True);save()
 except Exception as ex:
  e.update(status='uncertain'if any(i.get('status')in('submitting','accepted','uncertain')for i in e['items'])or e.get('price_result',{}).get('status')in('submitting','submitted','uncertain')else'partial'if any(i['status']=='verified'for i in e['items'])else'blocked',reason=type(ex).__name__+': '+str(ex)[:200]);save();raise
 finally:requests.sessions.Session.request=original
 print(json.dumps(dict(status=e['status'],ad_items=len(e['items']),prices=len(e['price_result']['items']),wb_writes=e['wb_writes'],telegram_calls=0,stock_writes=0,funding_writes=0)))
if __name__=='__main__':main()

