"""Exact prospective owner approval; durable one-shot WB writes, no TG/model."""
import copy,json,time,hashlib,requests,os
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import read_stock
from china_advertising_economic_review import model_rows
from china_price_apply import plan as price_request
ROOT='china_agent:owner_sales_recovery_apply:2026-11-22:v1'
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')}
 d['nm_settings']=sorted(d['nm_settings'],key=lambda n:n['nm_id']);return d
def expected_campaign(before,g,added=None,status=None):
 out=copy.deepcopy(before);members={n['nm_id']:n for n in out['nm_settings']}
 for nm in g.get('remove',[]):members.pop(nm,None)
 for n in added or[]:members[n['nm_id']]=copy.deepcopy(n)
 for x in g.get('bids',[]):members[x['nm_id']]['bids_kopecks'][g['zone']]=x['target']
 out['nm_settings']=list(members.values())
 if status is not None:out['status']=status
 return out
def main():
 io=AdvertisingIO();approval=io.get(ROOT+':approval');assert approval and approval['status']=='approved'and approval['owner_id']==5122667182 and approval['owner_instruction']=='Делай все'
 plan=approval['plan'];assert plan['day']=='2026-11-22'and plan['cabinet']=='token_3'and plan['telegram_send']is False
 assert datetime.now(timezone.utc)<datetime.fromisoformat(approval['expires_at']),'Approval expired'
 digest=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 e=io.get(ROOT+':execution')
 if e:
  assert e['plan_sha256']==digest,'Plan changed'
  if e['status']=='verified':print('Already verified; no writes');return
  assert os.environ.get('OWNER_RECOVERY_CONTINUE')=='true','Existing journal: explicit continuation required'
 else:
  e=dict(status='preflight',created_at=now(),approval_key=ROOT+':approval',plan_sha256=digest,groups=[],items=[],funding=[],campaigns=[],ops={},errors={},wb_writes=0,telegram_calls=0,model_calls=0,minimum_price_policy='seller_discounted_floor_preserve_blocks_v1')
  assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 allowed_write=None;orig=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);host=u.hostname or'';m=method.upper();body=kw.get('json');path=u.path+('?' + u.query if u.query else'')
  if 'telegram'in host or'openai'in host:raise ValueError('No Telegram/model')
  if host.endswith('moysklad.ru'):assert m=='GET'
  if host.endswith('wildberries.ru'):
   mutation=(m in('PATCH','DELETE','PUT')or m=='POST'and u.path not in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2126188')or u.path in('/adv/v0/start','/adv/v0/stop','/adv/v0/pause'))
   if mutation:assert allowed_write==(m,path,body),'Outside exact durable owner operation'
   else:assert m=='GET'or u.path in('/api/advert/v1/bids/min','/api/advert/v2/budget','/api/v3/stocks/2126188'),'Outside preflight reads'
  return orig(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.2);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store','Pragma':'no-cache'},json=body,timeout=(10,55));r.raise_for_status();return r.json()if r.content else{}
 def camp(cid):
  x=req('/api/advert/v2/adverts?ids='+str(cid)+'&owner_read='+str(time.time_ns()))['adverts'];assert len(x)==1 and x[0]['id']==cid and x[0]['currency']=='CNY';return x[0]
 def budget(cid):
  x=req('/api/advert/v2/budget','POST',dict(advertIds=[cid]))['adverts'];assert len(x)==1 and x[0]['advertId']==cid and x[0]['currency']=='CNY';return x[0]['total']
 def verified_state(cid,expected):
  last=None
  for _ in range(14):
   last=camp(cid)
   if norm(last)==norm(expected):
    time.sleep(2);again=camp(cid)
    if norm(again)==norm(expected):return again
   time.sleep(3)
  raise ValueError('Whole-package WB mismatch '+str(cid))
 def write(key,path,method='PATCH',body=None,price=False):
  nonlocal allowed_write
  old=e['ops'].get(key)
  assert old is None,'Existing operation not replayed: '+key
  e['ops'][key]=dict(status='submitting',path=path,method=method,body=body,submitted_at=now());save()
  allowed_write=(method,path,body)
  try:
   result=io.wb(path,method,body)if price else req(path,method,body)
  except Exception:
   e['ops'][key]['status']='uncertain';save();raise
  finally:allowed_write=None
  e['ops'][key].update(status='accepted',response=result);e['wb_writes']+=1;save();return result
 def receipt(g,after):
  g.update(status='verified',after=after,verified_at=now());save()
  key=ROOT+':campaign:'+str(g['cid']);value=dict(g,id=g['cid'])
  if io.get(key):io.put(key,value)
  else:assert io.create(key,value)
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(g['cid'])]=key
  io.put('china_agent:verified_campaign_state:v1',registry)if io.get('china_agent:verified_campaign_state:v1')else io.create('china_agent:verified_campaign_state:v1',registry)
 def fail(key,ex):e['errors'][key]=type(ex).__name__+': '+str(ex)[:240];save()
 try:
  if 'preflight'not in e:
   cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
   listing=req('/adv/v1/promotion/count');ids=sorted({x['advertId']for g in listing.get('adverts',[])for x in g.get('advert_list',[])})
   states=[]
   for start in range(0,len(ids),50):states+=req('/api/advert/v2/adverts?ids='+','.join(map(str,ids[start:start+50]))+'&owner_read='+str(time.time_ns()))['adverts']
   byid={c['id']:c for c in states};assert all(g['cid']in byid for g in plan['campaigns'])
   addids={n for g in plan['campaigns']for n in g.get('add',[])}
   raiseids={x['nm_id']for g in plan['campaigns']for x in g.get('bids',[])if x['target']>x['old']}
   nms=addids|raiseids|{p['nm_id']for p in plan['prices']}
   prices=current_prices(io,sorted(nms));assert {r['nm_id']for r in prices['rows']}==nms
   stock=read_stock([r['article']for r in prices['rows']],warehouse_role='msk');assert stock['coverage_complete']
   pub=published_stock(io,prices,sorted(nms));assert not pub['missing_nm_ids']
   inputs=io.get('china_agent:advertising_full_growth:2026-11-22:v1:inputs');assert inputs['status']=='complete'
   assert (datetime.now(timezone.utc)-datetime.fromisoformat(inputs['own']['observed_at'])).total_seconds()<48*3600
   def models(pp):return model_rows(dict(products=inputs['own'],prices=pp,stock=stock,fx=inputs['fx']),io.get('china_agent:new_ad_economics_policy:v1'),io.get('china_agent:expected_profit_delivery_model:v1'))
   model=models(prices);assert not model['missing']
   for n in nms:
    m=model['rows'][str(n)];assert m['stock_free']>0 and pub['amounts'][str(n)]>0 and m['expected_margin_before_ads_cny']>0,'Fresh stock/economics blocked '+str(n)
   targetprices=copy.deepcopy(prices)
   for p in targetprices['rows']:
    selected=next((x for x in plan['prices']if x['nm_id']==p['nm_id']),None)
    if selected:p['seller_price']=selected['target_cny']
   targetmodel=models(targetprices)
   assert all(targetmodel['rows'][str(x['nm_id'])]['expected_margin_before_ads_cny']>0 for x in plan['prices'])
   rawprices=io.prices([str(p['nm_id'])for p in plan['prices']]);price_items=[]
   for p in plan['prices']:
    s=dict(p,nm_id=str(p['nm_id']),action='Снижение');before=rawprices[s['nm_id']]
    if all(Decimal(str(z['discountedPrice']))==Decimal(str(s['target_cny']))for z in before['sizes'])and before['discount']==s['seller_discount']:
     price_items.append(dict(selection=s,status='applied',already_done=True,before=before,readback=before,verified_at=now()));continue
    request=price_request(s,before);assert request['discount']==s['seller_discount']and request['price']==s['target_base'],'Discount-preserving exact price required'
    oldlock=io.get('china_agent:price_write_lock:v1:'+s['nm_id'])or{};assert oldlock.get('status')not in('submitting','submitted','uncertain'),'Unfinished price write'
    price_items.append(dict(selection=s,status='ready',before=before,request=request))
   for spec in plan['campaigns']:
    c=byid[spec['cid']];assert c['id']!=42088552 and c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'
    assert c['settings']['placements'].get(spec['zone'])and not c['settings']['placements'].get('search'if spec['zone']=='recommendations'else'recommendations')
    assert c['status']in(9,11,7)
    old={n['nm_id']:n for n in c['nm_settings']};g=dict(cid=spec['cid'],before=c,spec=spec,status='ready')
    if spec.get('archive'):e['groups'].append(g);continue
    assert c['status']in(9,11)and(c['status']==9 or spec.get('resume'))
    for x in spec.get('bids',[]):assert x['nm_id']in old and old[x['nm_id']]['bids_kopecks'][spec['zone']]in(x['old'],x['target']),'Changed approved bid'
    missing=set(spec.get('add',[]))-set(old)
    duplicate=[(cp['id'],n['nm_id'])for cp in states if cp['status']in(9,11)and cp['id']!=c['id']and cp['id']not in spec.get('transfer_sources',[])and cp['settings']['placements'].get(spec['zone'])for n in cp['nm_settings']if n['nm_id']in missing]
    assert not duplicate,'Same-placement duplicate '+str(duplicate)
    quoteids={x['nm_id']for x in spec.get('bids',[])}
    if missing:quoteids.add(next(n['nm_id']for n in c['nm_settings']if n['subject']['id']==spec['subject']))
    if quoteids:
     typ='search'if spec['zone']=='search'else'recommendation'
     q=req('/api/advert/v1/bids/min','POST',dict(advert_id=c['id'],nm_ids=sorted(quoteids),payment_type='cpc',placement_types=[typ]))
     mins={n['nm_id']:next(b['value']for b in n['bids']if b['type']==typ and b['currency']=='CNY')for n in q['bids']};assert set(mins)==quoteids
     if missing:assert all(v<=spec['target']for v in mins.values()),'Category minimum increased'
     assert all(mins[x['nm_id']]<=x['target']and x['target']%cfg['cpcStep']==0 for x in spec.get('bids',[]))
     g['minima']=q
    if missing or spec.get('remove'):assert c.get('restrictions',{}).get('can_change_nms')is True
    if spec.get('remove'):assert set(old)-set(spec['remove']),'Cannot empty campaign'
    g['missing']=sorted(missing);e['groups'].append(g)
   e['items']=price_items;e['preflight']=dict(prices=prices,stock=stock,published=pub,economics=model,target_economics=targetmodel,protected=byid[42088552],config=cfg,observed_at=now());e['status']='running';save()
  # Price batch first. Locks and durable upload receipt prevent any replay.
  ready=[x for x in e['items']if x['status']=='ready']
  if ready:
   try:
    fresh=io.prices([x['selection']['nm_id']for x in ready])
    for x in ready:
     assert price_request(x['selection'],fresh[x['selection']['nm_id']])==x['request']
     lock='china_agent:price_write_lock:v1:'+x['selection']['nm_id'];old=io.get(lock)or{}
     assert old.get('execution')in(None,ROOT+':execution')or old.get('status')not in('submitting','submitted','uncertain')
     value=dict(execution=ROOT+':execution',status='submitting',selection=x['selection'],created_at=now());io.put(lock,value)if old else io.create(lock,value)
    if 'prices'not in e['ops']:
     result=write('prices','/api/v2/upload/task','POST',dict(data=[x['request']for x in ready]),price=True);assert type(result.get('id'))is int
     e['upload_id']=result['id'];save()
    else:assert e.get('upload_id'),'Uncertain price upload; no replay'
    for _ in range(24):
     state=io.wb('/api/v2/history/tasks?uploadID='+str(e['upload_id']));e['price_task']=state;save()
     if state.get('status')in(3,4,5,6):break
     time.sleep(10)
    assert state.get('status')in(3,5),'Price task not successful yet'
    details=io.wb('/api/v2/history/goods/task?uploadID='+str(e['upload_id'])+'&limit=1000&offset=0');assert details.get('uploadID')==e['upload_id'];e['price_details']=details
    fresh=io.prices([x['selection']['nm_id']for x in ready])
    for x in ready:
     s=x['selection'];p=fresh[s['nm_id']];goods=[n for n in details.get('historyGoods',[])if str(n.get('nmID'))==s['nm_id']]
     assert goods and not any(n.get('errorText')for n in goods)
     assert p['vendorCode']==s['article']and p['discount']==s['seller_discount']and p.get('clubDiscount')==s['club_discount']
     assert all(Decimal(str(z['price']))==Decimal(str(s['target_base']))and Decimal(str(z['discountedPrice']))==Decimal(str(s['target_cny']))for z in p['sizes'])
     x.update(status='applied',readback=p,verified_at=now());io.put('china_agent:price_write_lock:v1:'+s['nm_id'],dict(execution=ROOT+':execution',status='done',readback=p,upload_id=e['upload_id']));save()
     experience=dict(status='verified',started_at=x['verified_at'],execution_key=ROOT+':execution',action=dict(kind='price_change',nm_ids=[int(s['nm_id'])],before=s['current_cny'],after=s['target_cny']))
     io.create('china_agent:experience:v1:owner-recovery22-price-'+s['nm_id'],experience)
    e['ops']['prices']['status']='verified'
    from china_price_minimum import attach
    attach(e);save()
   except Exception as ex:fail('prices',ex)
  # Additions first; verified target membership precedes retiring either source.
  for g in e['groups']:
   if g['status']=='verified':continue
   spec=g['spec'];cid=g['cid'];key='campaign:'+str(cid)
   try:
    if spec.get('archive'):
     dep=next(x for x in e['groups']if x['cid']==spec['dependency']);assert dep['status']=='verified','Transfer target incomplete'
     target=camp(spec['dependency']);members={n['nm_id']:n for n in target['nm_settings']};assert all(n in members and members[n]['bids_kopecks'][spec['zone']]==28 for n in spec['transfer'])
     before=camp(cid);assert norm(before)==norm(g['before'])or before['status']==7
     if before['status']!=7:
      assert key+':archive'not in e['ops'],'Archive uncertain; no repeat'
      write(key+':archive','/adv/v0/stop?id='+str(cid),'GET')
     after=verified_state(cid,expected_campaign(g['before'],spec,status=7));receipt(g,after);continue
    current=camp(cid);assert norm(current)==norm(g['before']),'Campaign changed since preflight'
    old={n['nm_id']:n for n in current['nm_settings']};missing=set(g.get('missing',[]));remove=set(spec.get('remove',[]))&set(old)
    if missing or remove:
     body=dict(nms=[dict(advert_id=cid,nms=dict(add=sorted(missing),delete=sorted(remove)))])
     write(key+':members','/adv/v0/auction/nms',body=body)
     for _ in range(14):
      current=camp(cid);actual={n['nm_id']:n for n in current['nm_settings']}
      if set(actual)==(set(old)|missing)-remove and all(actual[n]==v for n,v in old.items()if n not in remove):break
      time.sleep(3)
     else:raise ValueError('Membership readback mismatch')
     # Exact new-member minima and protected unrelated fields.
     assert current['status']==g['before']['status']and current['settings']==g['before']['settings']
     if missing:
      typ='search'if spec['zone']=='search'else'recommendation';q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=sorted(missing),payment_type='cpc',placement_types=[typ]));g['new_member_minima']=q
      mins={r['nm_id']:next(b['value']for b in r['bids']if b['type']==typ and b['currency']=='CNY')for r in q['bids']};assert set(mins)==missing and all(v<=spec['target']for v in mins.values())
    actual={n['nm_id']:n for n in current['nm_settings']};bids=[]
    for nm in missing:
     assert actual[nm]['subject']['id']==spec['subject']and actual[nm]['bids_kopecks'].get('search'if spec['zone']=='recommendations'else'recommendations',0)==0
     if actual[nm]['bids_kopecks'][spec['zone']]!=spec['target']:bids.append(dict(nm_id=nm,bid_kopecks=spec['target'],placement=spec['zone']))
    for x in spec.get('bids',[]):
     if actual[x['nm_id']]['bids_kopecks'][spec['zone']]!=x['target']:bids.append(dict(nm_id=x['nm_id'],bid_kopecks=x['target'],placement=spec['zone']))
    if bids:write(key+':bids','/api/advert/v1/bids',body=dict(bids=[dict(advert_id=cid,nm_bids=bids)]))
    added=[copy.deepcopy(actual[n])for n in missing]
    for n in added:n['bids_kopecks'][spec['zone']]=spec['target']
    expected=expected_campaign(g['before'],spec,added)
    after=verified_state(cid,expected)
    if spec.get('resume')and after['status']==11:
     assert key+':start'not in e['ops'];write(key+':start','/adv/v0/start?id='+str(cid),'GET');expected['status']=9;after=verified_state(cid,expected)
    receipt(g,after)
    for op in e['ops'].values():
     if op.get('status')=='accepted'and (op['body']or{}).get('bids',[{}])[0].get('advert_id')==cid:op['status']='verified'
    save()
   except Exception as ex:
    g['status']='uncertain'if any(k.startswith(key)and v['status']in('submitting','accepted','uncertain')for k,v in e['ops'].items())else'blocked';fail(key,ex)
  # Cash-only owner exceptions do not change the protected campaign's ads.
  for f in plan['funding']:
   cid=f['cid'];key='fund:'+str(cid);s=next((x for x in e['funding']if x['cid']==cid),None)
   if s and s['status']=='verified':continue
   if s is None:s=dict(cid=cid,status='preflight',amount=f['amount']);e['funding'].append(s);save()
   try:
    dep=next((g for g in e['groups']if g['cid']==cid),None)
    assert dep is None or dep['status']=='verified','Campaign changes incomplete; funding deferred'
    before=camp(cid);assert before['status']==9,'Funding target no longer active'
    if cid==42088552:assert norm(before)==norm(e['preflight']['protected']),'Protected campaign changed'
    cash=budget(cid);s.update(before=before,before_budget=cash);save()
    if cash>=f['target_balance']:s.update(status='verified',already_done=True,after=before,after_budget=cash,verified_at=now());save();continue
    assert cash<=f['balance_before']+2,'Campaign funded since owner proposal; reconcile before another deposit'
    if key in e['ops']:raise ValueError('Prior deposit not replayed')
    cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and cfg['minTopUp']<=f['amount']*100
    bal=req('/adv/v1/balance');typ=0 if bal.get('balance',0)>=f['amount']else 1 if bal.get('net',0)>=f['amount']else None;assert bal.get('currency')=='CNY'and typ is not None,'Available cash insufficient'
    result=write(key,'/adv/v1/budget/deposit?id='+str(cid),'POST',dict(sum=f['amount'],type=typ));s['deposit_response']=result;save()
    after=verified_state(cid,before);after_budget=budget(cid);s.update(after=after,after_budget=after_budget)
    assert after_budget>=cash+f['amount']-2,'Deposit balance readback not confirmed'
    s.update(status='verified',verified_at=now());e['ops'][key]['status']='verified'
    op=copy.deepcopy(e['ops'][key]);op.update(status='verified',verified_at=s['verified_at'])
    funding_receipt=dict(id=key,status='verified',before=before,after=after,before_budget=cash,after_budget=after_budget,amount_cny=f['amount'],verified_at=s['verified_at'],steps=dict(deposit=op))
    e.setdefault('campaigns',[]).append(funding_receipt);save()
    io.create(ROOT+':funding:'+str(cid),funding_receipt)
   except Exception as ex:s['status']='uncertain'if key in e['ops']else'blocked';fail(key,ex)
  # Final package readback catches reappearing exclusions or lost bid changes.
  final=[]
  for g in e['groups']:
   if g['status']!='verified':continue
   try:final.append(verified_state(g['cid'],g['after']))
   except Exception as ex:g['status']='uncertain';fail('final:'+str(g['cid']),ex)
  protected=camp(42088552);assert norm(protected)==norm(e['preflight']['protected']),'Protected advertising changed'
  e['protected_after']=protected;e['package_readback']=final
  day=datetime.now(ZoneInfo('Europe/Moscow')).date();tracking=io.get('china_agent:new_ad_tests:tracking:v1')or dict(plans={})
  for g in e['groups']:
   if g['status']!='verified':continue
   nm_ids=g['spec'].get('add',[])
   if nm_ids:
    tracking.setdefault('plans',{})['owner-recovery22-'+str(g['cid'])]=dict(status='active',campaign_ids=[g['cid']],started_at=g['verified_at'],nm_ids=nm_ids,bid_minor=g['spec']['target'],placement=g['spec']['zone'],execution_key=ROOT+':campaign:'+str(g['cid']),auto_topup=False,existing_reports=True,evaluation=dict(excluded_change_day=str(day),first_full_day=str(day+timedelta(days=1)),earliest_review=str(day+timedelta(days=2))))
  io.put('china_agent:new_ad_tests:tracking:v1',tracking)if io.get('china_agent:new_ad_tests:tracking:v1')else io.create('china_agent:new_ad_tests:tracking:v1',tracking)
  e['reports_registered']=True;e['status']='verified'if all(g['status']=='verified'for g in e['groups'])and all(x['status']=='applied'for x in e['items'])and len(e['funding'])==len(plan['funding'])and all(f['status']=='verified'for f in e['funding'])else'partial_attention'
  e['completed_at']=now();save()
 except Exception as ex:e['status']='preflight_blocked'if e['wb_writes']==0 else'partial_attention';fail('root',ex);raise
 print(json.dumps(dict(status=e['status'],wb_writes=e['wb_writes'],errors=e['errors'],telegram_calls=0,model_calls=0)))
if __name__=='__main__':main()

