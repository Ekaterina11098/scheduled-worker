"""Owner seven exact risk actions; protected GUA; no funding/prices/Telegram."""
import copy,json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices
from china_moysklad_read import Reader
ROOT='china_agent:owner_fourrc_apply27:v1'
io=AdvertisingIO();a=io.get(ROOT+':approval')
assert a['status']=='approved'and a['owner_id']==5122667182 and not a['funding']and not a['prices']and not a['telegram_send']
actions=a['actions'];assert len(actions)==7 and {x['campaign_id']for x in actions}=={41155909,41967612,42068186}
assert all(x['campaign_id']not in a['protected_campaign_ids']for x in actions)
def now():return datetime.now(timezone.utc).isoformat()
prior=io.get(ROOT+':execution')
if prior:raise SystemExit('Existing execution: reconcile readbacks, never replay')
e=dict(status='preflight',created_at=now(),approval_key=ROOT+':approval',actions=actions,ops={},groups=[],wb_writes=0,price_writes=0,funding_calls=0,telegram_calls=0)
assert io.create(ROOT+':execution',e)
def save():io.put(ROOT+':execution',copy.deepcopy(e))
orig=requests.sessions.Session.request;allowed=None
def guard(s,method,url,*args,**kw):
 u=urlparse(url);m=method.upper();p=u.path
 safe=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and p.startswith('/rest/v1/')
 safe=safe or u.hostname=='advert-api.wildberries.ru'and(m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config')or m=='POST'and p=='/api/advert/v1/bids/min')
 safe=safe or u.hostname=='discounts-prices-api.wildberries.ru'and m=='GET'and p=='/api/v2/list/goods/filter'
 safe=safe or u.hostname=='api.moysklad.ru'and m=='GET'and p.startswith('/api/remap/1.2/')
 exact=(m,p+('?'+u.query if u.query else''),kw.get('json'))
 assert safe or u.hostname=='advert-api.wildberries.ru'and allowed==exact,'Outside exact owner operation'
 return orig(s,method,url,*args,**kw)
requests.sessions.Session.request=guard
def req(path,method='GET',body=None):
 time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache'},timeout=(10,45));r.raise_for_status();return r.json()if r.content else{}
def camp(cid):
 c=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(c)==1 and c[0]['id']==cid;return c[0]
def norm(c):
 z={k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')};z['nm_settings']=sorted(z['nm_settings'],key=lambda n:n['nm_id']);return z
def quote(cid,nms,zone):
 z='recommendation'if zone=='recommendations'else zone
 q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=nms,payment_type='cpc',placement_types=[z]))
 return {str(n['nm_id']):next(b['value']for b in n['bids']if b['type']==z and b['currency']=='CNY')for n in q['bids']}
def write(key,path,method,body=None):
 global allowed
 assert key not in e['ops'],'No write replay'
 assert io.get(ROOT+':approval')==a,'Approval changed'
 e['ops'][key]=dict(status='submitting',path=path,method=method,body=body,submitted_at=now());save();allowed=(method,path,body)
 try:resp=req(path,method,body)
 except Exception:
  e['ops'][key]['status']='uncertain';save();raise
 finally:allowed=None
 e['ops'][key].update(status='accepted',response=resp);e['wb_writes']+=1;save()
def verify(cid,expected):
 for attempt in range(12):
  c=camp(cid)
  if norm(c)==norm(expected):
   time.sleep(2)
   again=camp(cid)
   if norm(again)==norm(expected):return again
  time.sleep(3)
 raise ValueError('Whole campaign verification mismatch '+str(cid))
try:
 cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
 allids=[41155909,41967612,42068186,41779660,42088552]
 states={c['id']:c for c in req('/api/advert/v2/adverts?ids='+','.join(map(str,allids)))['adverts']};assert set(states)==set(allids)
 e['protected_before']={str(cid):states[cid]for cid in a['protected_campaign_ids']}
 nms=sorted({x.get('nm_id')for x in actions if x.get('nm_id')}|{1473243898})
 prices=current_prices(io,nms);assert {p['nm_id']for p in prices['rows']}==set(nms)
 approved_rows={r['nm']:r for r in io.get(a['proposal_key'])['rows']};models={}
 st=Reader().stock([approved_rows[n]['a']for n in nms],'msk');assert st['coverage_complete']
 cur=requests.get('https://api.moysklad.ru/api/remap/1.2/entity/currency',headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip'},timeout=(10,40));cur.raise_for_status();cur=cur.json()
 assert len([x for x in cur['rows']if x.get('default')])==1 and next(x for x in cur['rows']if x.get('default'))['isoCode']=='CNY'
 # Retain the dated observed buyout/fees/logistics from reviewed proposal; fresh native CNY cost and price.
 old=io.get('china_agent:advertising_full_growth:2026-11-27:v1:inputs')['economics']['rows']
 for p in prices['rows']:
  n=p['nm_id'];assert p['article']==approved_rows[n]['a']and p['currency']=='CNY'and abs(float(p['seller_price'])-approved_rows[n]['price'])<.001,'Reviewed price changed'
  m=old[str(n)];s=next(x for x in st['rows']if x['article'].casefold()==p['article'].casefold())
  profit=m['buyout']*(p['seller_price']*(1-(m['commission_pct']+m['tax_pct']+m['payment_reserve_pct'])/100)-s['price']/100)-m['logistics_cny']-m['handling_rub']/m['fx_rub_per_cny']-.08*p['seller_price']
  models[str(n)]=dict(profit_at_drr8_cny=profit,cost_cny=s['price']/100,buyout=m['buyout'],sample_size=m['sample_size'],preliminary=True,previous_costs_retained=True)
 e['preflight']=dict(config=cfg,prices=prices,stock=st,economics=models,observed_at=now());save()
 for cid in(41155909,41967612,42068186):
  c=states[cid];assert c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'and c['status']in(9,11)
  xs=[x for x in actions if x['campaign_id']==cid];oldn={n['nm_id']:n for n in c['nm_settings']}
  for x in xs:
   if x['kind']=='pause_campaign':assert set(oldn)==set(x['nm_ids'])
   elif x['kind']=='ad_set_bid':assert x['nm_id']in oldn and oldn[x['nm_id']]['bids_kopecks'][x['placement']]in(x['old_minor'],x['target_minor'])
   elif x['nm_id']in oldn:assert oldn[x['nm_id']]['bids_kopecks'][x['placement']]==x['old_minor']
  reduce=[x for x in xs if x['kind']=='ad_set_bid']
  mins=quote(cid,[x['nm_id']for x in reduce],'search')if reduce else{}
  assert all(mins[str(x['nm_id'])]<=x['target_minor']and x['target_minor']%cfg['cpcStep']==0 for x in reduce)
  remove=[x['nm_id']for x in xs if x['kind']=='ad_exclude_sku'and x['nm_id']in oldn]
  if remove:assert c['restrictions']['can_change_nms']and set(oldn)-set(remove)
  e['groups'].append(dict(cid=cid,before=c,actions=xs,minima=mins,remove=remove,status='ready'))
 save()
 for g in e['groups']:
  cid=g['cid'];c=camp(cid);assert norm(c)==norm(g['before']),'Concurrent state changed before operation'
  expected=copy.deepcopy(c)
  if any(x['kind']=='pause_campaign'for x in g['actions']):
   if c['status']==9:write(str(cid)+':pause','/adv/v0/pause?id='+str(cid),'GET')
   expected['status']=11
  else:
   if g['remove']:
    write(str(cid)+':exclude','/adv/v0/auction/nms','PATCH',dict(nms=[dict(advert_id=cid,nms=dict(add=[],delete=g['remove']))]))
    expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']not in g['remove']]
    verify(cid,expected)
   for x in g['actions']:
    if x['kind']!='ad_set_bid':continue
    current=camp(cid);assert norm(current)==norm(expected)
    n=next(n for n in expected['nm_settings']if n['nm_id']==x['nm_id'])
    if n['bids_kopecks'][x['placement']]!=x['target_minor']:
     write(str(cid)+':bid','/api/advert/v1/bids','PATCH',dict(bids=[dict(advert_id=cid,nm_bids=[dict(nm_id=x['nm_id'],placement=x['placement'],bid_kopecks=x['target_minor'])])]))
    n['bids_kopecks'][x['placement']]=x['target_minor']
  after=verify(cid,expected);g.update(status='verified',after=after,verified_at=now());save()
  key=ROOT+':campaign:'+str(cid);assert io.create(key,dict(g,status='verified'))
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=key
  io.put('china_agent:verified_campaign_state:v1',registry)if io.get('china_agent:verified_campaign_state:v1')else io.create('china_agent:verified_campaign_state:v1',registry)
  for x in g['actions']:
   kind='composition_change'if x['kind']=='ad_exclude_sku'else'bid_change'if x['kind']=='ad_set_bid'else'pause_campaign'
   ns=x.get('nm_ids')or[x['nm_id']]
   io.create('china_agent:experience:v1:owner-fourrc27-'+str(cid)+'-'+str(ns[0]),dict(status='verified',started_at=g['verified_at'],execution_key=key,action=dict(kind=kind,nm_ids=ns,campaign_id=cid,source_action=x)))
 final={c['id']:c for c in req('/api/advert/v2/adverts?ids='+','.join(map(str,allids)))['adverts']}
 for g in e['groups']:assert norm(final[g['cid']])==norm(g['after'])
 e['protected_after']={str(cid):final[cid]for cid in a['protected_campaign_ids']}
 assert all(norm(e['protected_after'][str(cid)])==norm(e['protected_before'][str(cid)])for cid in a['protected_campaign_ids']),'Protected campaign concurrently changed'
 e.update(status='verified',verified_at=now(),reporting_registered=True);save()
except Exception as ex:
 e.update(status='needs_reconciliation'if e['ops']else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save()
finally:requests.sessions.Session.request=orig
print(json.dumps(dict(status=e['status'],error=e.get('error'),wb_writes=e['wb_writes'])))
