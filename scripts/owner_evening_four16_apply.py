"""Four exact owner actions. No funding, TG, model, price or stock writes; durable checkpoints."""
import os,json,copy,time
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_evening_four:2026-11-16:v1'
ADD=1473243903;DST=40933588;SEARCH=41298169
REMOVALS={DST:{1473243448,1473245505},SEARCH:{1473244341}}
def stamp():return datetime.now(timezone.utc).isoformat()
def keyed(c):return {n['nm_id']:n for n in c['nm_settings']}
def projected(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','bid_type','settings')};d['nm_settings']=sorted(copy.deepcopy(c['nm_settings']),key=lambda n:n['nm_id']);return d
def membership_ok(before,after,add,remove):
 if any(before[k]!=after[k]for k in('id','status','currency','bid_type','settings')):return False
 old=keyed(before);new=keyed(after)
 if set(new)!=(set(old)|set(add))-set(remove):return False
 if any(new[nm]!=n for nm,n in old.items()if nm not in remove):return False
 return all(new[nm]['subject']['id']==50 for nm in add)
def main():
 db=Cache();a=db.get(ROOT+':authorization')
 expected=dict(add=dict(campaign_id=DST,nm_id=ADD,bid_minor=28,placement='recommendations'),remove=[dict(campaign_id=DST,nm_id=1473243448),dict(campaign_id=DST,nm_id=1473245505),dict(campaign_id=SEARCH,nm_id=1473244341)],fund_cny=0,telegram_send=False)
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['source_channel']=='codex'and a['scope']==expected
 def live():assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'].replace('Z','+00:00'))
 live();validate_identity(db,WB())
 e=dict(status='preflight',authorization_key=ROOT+':authorization',created_at=stamp(),steps=[],items=[],wb_writes=0,telegram_calls=0,model_calls=0,funded_cny=0,telegram_delivery_suppressed_by_owner=True)
 if not db.create(ROOT+':execution',e):raise RuntimeError('Execution exists; no automatic replay; inspect journal')
 def save():db.put(ROOT+':execution',json.loads(json.dumps(e)))
 token=os.environ['WB_TOKEN_3']
 def req(path,method='GET',body=None):
  time.sleep(1);r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':token},json=body,timeout=(10,50))
  if not r.ok:raise RuntimeError('WB HTTP '+str(r.status_code))
  return r.json()if r.content else{}
 def campaign(cid):
  rows=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(rows)==1 and rows[0]['id']==cid;return rows[0]
 def verify(fn):
  for attempt in range(8):
   try:
    result=fn()
    if result is not None:return result
   except(requests.Timeout,requests.ConnectionError):pass
   if attempt<7:time.sleep(5)
  raise RuntimeError('WB readback unconfirmed; mutation must not repeat')
 def write(kind,path,body,check):
  live();assert not any(s['kind']==kind for s in e['steps'])
  step=dict(kind=kind,status='submitting',path=path,method='PATCH',body=body,submitted_at=stamp());e['steps'].append(step);save()
  try:
   step['response']=req(path,'PATCH',body);step['status']='accepted';e['wb_writes']+=1;save()
   after=verify(check);step.update(status='verified',readback=after,verified_at=stamp());save();return after
  except Exception as err:
   step.update(status='uncertain',reason=type(err).__name__+': '+str(err)[:160]);e['status']='uncertain';save();raise
 try:
  before={cid:campaign(cid)for cid in(DST,SEARCH)}
  for cid,c in before.items():
   assert c['status']==9 and c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'and c['restrictions']['can_change_nms']
   assert all(n['subject']['id']==50 for n in c['nm_settings'])
  assert before[DST]['settings']['placements']==dict(search=False,recommendations=True)
  assert before[SEARCH]['settings']['placements']==dict(search=True,recommendations=False)
  cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'and 28%cfg['cpcStep']==0 and 28<=cfg['cpcMaxBid']
  member=next(n['nm_id']for n in before[DST]['nm_settings']if n['nm_id']not in REMOVALS[DST])
  quote=req('/api/advert/v1/bids/min','POST',dict(advert_id=DST,nm_ids=[member],payment_type='cpc',placement_types=['recommendation']))
  minima=[b['value']for r in quote['bids']if r['nm_id']==member for b in r['bids']if b['type']=='recommendation'and b['currency']=='CNY'];assert len(minima)==1 and minima[0]<=28
  from china_morning_readiness import current_prices,published_stock
  from china_moysklad_read import read_stock
  class Prices:
   token=os.environ['WB_TOKEN_3']
   def wb(self,path):
    r=requests.get('https://discounts-prices-api.wildberries.ru'+path,headers={'Authorization':self.token},timeout=(10,45));r.raise_for_status();return r.json()['data']
  io=Prices();prices=current_prices(io,[ADD]);pub=published_stock(io,prices,[ADD]);stock=read_stock(['534-NoelBag-emerald'])
  assert prices['rows'][0]['article']=='534-NoelBag-emerald'and prices['rows'][0]['seller_price']==201.5
  assert stock['coverage_complete']and len(stock['rows'])==1 and stock['rows'][0]['stock']-stock['rows'][0]['reserve']>0 and pub['amounts'][str(ADD)]>0
  proposal=db.get(a['proposal_key']);p=next(x for x in proposal['actions']if x['kind']=='ad_add_sku'and x['nm_id']==ADD)
  assert p['target_cny']==.28 and p['campaign_id']==DST and p['unknown_reverse_shared_costs']is True
  margin=p['buyout']*(201.5*.72-stock['rows'][0]['price']/100/12.3149)-p['logistics_cny'];assert margin>0
  e['preflight']=dict(before=before,config=cfg,minimum=quote,minimum_basis='owner_shared_subject50_rule',prices=prices,published_stock=pub,msk_stock=stock,preliminary_margin_before_ads_cny=margin,budgets=req('/api/advert/v2/budget','POST',dict(advertIds=[DST,SEARCH])));save()
  for cid in(DST,SEARCH):
   writes_before=e['wb_writes']
   initial=before[cid];assert projected(campaign(cid))==projected(initial),'Campaign changed since fresh preflight'
   add=[ADD]if cid==DST and ADD not in keyed(initial)else[];remove=sorted(REMOVALS[cid]&set(keyed(initial)))
   current=initial
   if add or remove:
    def checked(cid=cid,initial=initial,add=add,remove=remove):
     c=campaign(cid);return c if membership_ok(initial,c,add,remove)else None
    current=write('membership:'+str(cid),'/adv/v0/auction/nms',dict(nms=[dict(advert_id=cid,nms=dict(add=add,delete=remove))]),checked)
   if cid==DST:
    assert ADD in keyed(current)
    if keyed(current)[ADD]['bids_kopecks']['recommendations']!=28:
     before_bid=copy.deepcopy(current);wanted=copy.deepcopy(current);keyed(wanted)[ADD]['bids_kopecks']['recommendations']=28
     def bid_checked():
      c=campaign(DST);return c if projected(c)==projected(wanted)else None
     current=write('bid:'+str(DST),'/api/advert/v1/bids',dict(bids=[dict(advert_id=DST,nm_bids=[dict(nm_id=ADD,placement='recommendations',bid_kopecks=28)])]),bid_checked)
    assert keyed(current)[ADD]['bids_kopecks']['recommendations']==28
   assert not REMOVALS[cid]&set(keyed(current))
   child=ROOT+':campaign:'+str(cid);receipt=dict(status='verified',before=initial,after=current,verified_at=stamp(),parent=ROOT+':execution',already_done=e['wb_writes']==writes_before,telegram_delivery=False)
   assert db.create(child,receipt)
   reg=db.get('china_agent:verified_campaign_state:v1')or{};reg[str(cid)]=child;db.put('china_agent:verified_campaign_state:v1',reg)
   e['items'].append(dict(campaign_id=cid,status='verified',receipt_key=child,before=initial,after=current));save()
  final={cid:campaign(cid)for cid in(DST,SEARCH)}
  for item in e['items']:assert projected(final[item['campaign_id']])==projected(item['after'])
  e.update(status='verified',verified_at=stamp(),final_readback=final,final_budgets=req('/api/advert/v2/budget','POST',dict(advertIds=[DST,SEARCH])));save()
 except Exception as err:
  if e['status']!='uncertain':e.update(status='attention_required'if e['wb_writes']else'blocked',reason=type(err).__name__+': '+str(err)[:250]);save()
  raise
 print(json.dumps(dict(status=e['status'],wb_writes=e['wb_writes'],funded_cny=0,telegram_calls=0,model_calls=0)))
if __name__=='__main__':
 old=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);method=method.upper();body=kw.get('json')
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and method in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':
   ok=method=='GET'and u.path in('/api/advert/v2/adverts','/api/advert/v1/config','/adv/v1/supplier/settings')or method=='POST'and u.path in('/api/advert/v1/bids/min','/api/advert/v2/budget')
   if method=='PATCH'and u.path=='/adv/v0/auction/nms':
    ok=isinstance(body,dict)and set(body)=={'nms'}and len(body['nms'])==1
    if ok:
     row=body['nms'][0];cid=row['advert_id'];changes=row['nms'];ok=cid in REMOVALS and set(changes)=={'add','delete'}and set(changes['delete'])<=REMOVALS[cid]and changes['add']in([ADD],[])and(not changes['add']or cid==DST)
   if method=='PATCH'and u.path=='/api/advert/v1/bids':ok=body==dict(bids=[dict(advert_id=DST,nm_bids=[dict(nm_id=ADD,placement='recommendations',bid_kopecks=28)])])
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=method=='GET'and u.path=='/api/v2/list/goods/filter'
  elif u.hostname=='marketplace-api.wildberries.ru':ok=method=='POST'and u.path=='/api/v3/stocks/2126188'
  elif u.hostname=='api.moysklad.ru':ok=method=='GET'and u.path.startswith('/api/remap/1.2/')
  else:ok=False
  assert ok,'Network scope excludes funding/TG/models and unrelated mutations'
  return old(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:main()
 finally:requests.sessions.Session.request=old

