"""Exact owner approved reach restoration. No funding/prices/Telegram."""
import copy,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
ROOT='china_agent:owner_reach15_apply27:v1'
io=AdvertisingIO()
def now():return datetime.now(timezone.utc).isoformat()
scope=io.get('china_agent:owner_reach15_27:v1:scope')['items']
plan=io.get('china_agent:shared_memory:v1:work:note:reach15-proposal-20261127')['recommendations']
targets=[dict(x,nm=next(y['nm']for y in scope if y['article']==x['a']))for x in plan if not x['action'].startswith('hold')]
assert len(targets)==11 and sum(x['current'] is not None for x in targets)==10
e=io.get(ROOT+':execution')
if e:assert not e.get('ops') and e.get('status')=='blocked','Existing write journal; reconcile only'
e=dict(status='preflight',created_at=now(),owner_instruction='усиль 10 товаров и верни 92, остальные четыре оставь без изменений',targets=targets,ops={},groups=[],errors={},telegram_calls=0,funding_calls=0,price_writes=0)
io.put(ROOT+':execution',e) if io.get(ROOT+':execution') else io.create(ROOT+':execution',e)
def save():io.put(ROOT+':execution',copy.deepcopy(e))
orig=requests.sessions.Session.request;allowed=None
def guard(s,method,url,*a,**kw):
 u=urlparse(url);m=method.upper();p=u.path
 if 'telegram'in (u.hostname or'')or'openai'in(u.hostname or''):raise ValueError('No sends/models')
 if 'wildberries.ru'in(u.hostname or''):
  safe=m=='GET'and p in('/api/advert/v2/adverts','/api/advert/v1/config','/api/v2/list/goods/filter')or m=='POST'and p in('/api/advert/v1/bids/min','/api/v3/stocks/2126188')
  assert safe or allowed==(m,p,kw.get('json')),'Outside exact operation'
 return orig(s,method,url,*a,**kw)
requests.sessions.Session.request=guard
def req(path,method='GET',body=None):
 time.sleep(1.3)
 r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache'},timeout=(10,45))
 r.raise_for_status();return r.json()if r.content else{}
def camp(cid):
 a=req('/api/advert/v2/adverts?ids='+str(cid))['adverts'];assert len(a)==1 and a[0]['id']==cid;return a[0]
def norm(c):
 d={k:copy.deepcopy(c[k])for k in('id','status','currency','settings','bid_type','nm_settings')};d['nm_settings']=sorted(d['nm_settings'],key=lambda x:x['nm_id']);return d
def quote(cid,nms,zone):
 z='recommendation'if zone=='recommendations'else zone
 q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=nms,payment_type='cpc',placement_types=[z]))
 return {x['nm_id']:next(b['value']for b in x['bids']if b['type']==z and b['currency']=='CNY')for x in q['bids']}
def write(k,path,body):
 global allowed
 assert k not in e['ops']
 e['ops'][k]=dict(status='submitting',path=path,body=body,submitted_at=now());save();allowed=('PATCH',path,body)
 try:r=req(path,'PATCH',body)
 except Exception:
  e['ops'][k]['status']='uncertain';save();raise
 finally:allowed=None
 e['ops'][k].update(status='accepted',response=r);save()
try:
 cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
 ids=[x['nm']for x in targets];prices=current_prices(io,ids);pub=published_stock(io,prices,ids)
 assert not pub['missing_nm_ids'] and all(pub['amounts'][str(n)]>0 for n in ids)
 assert all(abs(next(float(p['seller_price'])for p in prices['rows']if p['nm_id']==x['nm'])-x['price'])<.001 for x in targets),'Price changed since approval'
 e['preflight']=dict(prices=prices,published=pub,config=cfg,observed_at=now(),economics_source='china_agent:advertising_full_growth:2026-11-26:v1:inputs:midday',economics_limitation='Previously disclosed verified RUB COGS; fresh stock cost units not accepted')
 for cid in sorted(set(x['campaign']for x in targets)):
  c=camp(cid);assert cid!=42088552 and c['status']==9 and c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'
  zone='search'if cid==42068186 else'recommendations';assert c['settings']['placements'][zone]
  xs=[x for x in targets if x['campaign']==cid];members={n['nm_id']:n for n in c['nm_settings']}
  missing=[x['nm']for x in xs if x['nm']not in members];assert all(x['current']is None for x in xs if x['nm']in missing)
  assert len(members)+len(missing)<=50
  for x in xs:
   if x['nm']in members:assert members[x['nm']]['bids_kopecks'][zone]in(round(x['current']*100)if x['current']is not None else 30,round(x['proposed']*100))
  existing=[x['nm']for x in xs if x['nm']in members];mins=quote(cid,existing,zone)
  assert all(mins[x['nm']]<=round(x['proposed']*100) and round(x['proposed']*100)%cfg['cpcStep']==0 for x in xs if x['nm']in members)
  if missing:assert c['restrictions']['can_change_nms'] and max(mins.values())<=30
  e['groups'].append(dict(cid=cid,zone=zone,before=c,targets=xs,missing=missing,minima={str(k):v for k,v in mins.items()},status='ready'))
 save()
 for g in e['groups']:
  cid=g['cid'];zone=g['zone'];c=camp(cid);assert norm(c)==norm(g['before']),'Concurrent campaign change'
  expected=copy.deepcopy(c)
  if g['missing']:
   write(str(cid)+':add','/adv/v0/auction/nms',dict(nms=[dict(advert_id=cid,nms=dict(add=g['missing'],delete=[]))]))
   for attempt in range(12):
    c=camp(cid)
    if set(n['nm_id']for n in c['nm_settings'])==set(n['nm_id']for n in expected['nm_settings'])|set(g['missing']):break
    time.sleep(3)
   else:raise ValueError('Membership not confirmed')
   new=[copy.deepcopy(n)for n in c['nm_settings']if n['nm_id']in g['missing']]
   expected['nm_settings']+=new
   assert norm(c)==norm(expected),'Unrelated campaign fields changed'
   g['new_minima']={str(k):v for k,v in quote(cid,g['missing'],zone).items()};assert all(v<=30 for v in g['new_minima'].values());save()
  actual={n['nm_id']:n for n in c['nm_settings']}
  bids=[dict(nm_id=x['nm'],bid_kopecks=round(x['proposed']*100),placement=zone)for x in g['targets']if actual[x['nm']]['bids_kopecks'][zone]!=round(x['proposed']*100)]
  if bids:write(str(cid)+':bids','/api/advert/v1/bids',dict(bids=[dict(advert_id=cid,nm_bids=bids)]))
  for n in expected['nm_settings']:
   x=next((x for x in g['targets']if x['nm']==n['nm_id']),None)
   if x:n['bids_kopecks'][zone]=round(x['proposed']*100)
  for attempt in range(12):
   after=camp(cid)
   if norm(after)==norm(expected):
    time.sleep(2)
    if norm(camp(cid))==norm(expected):break
   time.sleep(3)
  else:raise ValueError('WB full state mismatch')
  g.update(status='verified',after=after,verified_at=now());save()
  key=ROOT+':campaign:'+str(cid);assert io.create(key,dict(g,status='verified'))
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=key
  io.put('china_agent:verified_campaign_state:v1',registry)if io.get('china_agent:verified_campaign_state:v1')else io.create('china_agent:verified_campaign_state:v1',registry)
  for x in g['targets']:
   io.create('china_agent:experience:v1:reach15-27-'+str(cid)+'-'+str(x['nm']),dict(status='verified',started_at=g['verified_at'],execution_key=ROOT+':execution',action=dict(kind='bid_change'if x['current']is not None else'addition',nm_ids=[x['nm']],campaign_id=cid,before=x['current'],after=x['proposed'])))
 e.update(status='verified',verified_at=now());save()
except Exception as ex:
 e.update(status='needs_reconciliation'if e['ops']else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save()
finally:requests.sessions.Session.request=orig
print(json.dumps(dict(status=e['status'],error=e.get('error'),groups=[dict(cid=g['cid'],status=g['status'])for g in e['groups']])))
