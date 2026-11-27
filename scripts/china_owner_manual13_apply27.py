"""Exact owner-approved 12 bids + one search exclusion. No prices/funding/TG."""
import requests,copy,time,os,json
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_morning_readiness import current_prices,published_stock
from china_moysklad_read import Reader
ROOT='china_agent:owner_manual13_apply27:v1'
io=AdvertisingIO();auth=io.get(ROOT+':approval')
assert auth['status']=='approved' and auth['owner_id']==5122667182
targets=auth['targets'];assert len(targets)==13
assert sum(x['kind']=='bid'and x['target']>x['old']for x in targets)==4
assert sum(x['kind']=='bid'and x['target']<x['old']for x in targets)==8
assert [x['nm']for x in targets if x['kind']=='exclude']==[1473243444]
assert all(x['cid']in[40933588,41270309,41298169]for x in targets)
assert auth['no_telegram']and auth['no_funding']and auth['no_price_changes']
def now():return datetime.now(timezone.utc).isoformat()
old=io.get(ROOT+':execution')
if old and old.get('status')=='verified':raise SystemExit('Already verified; no repeats')
if old and old.get('ops'):raise SystemExit('Existing operations; reconciliation only, no automatic replay')
e=dict(status='preflight',created_at=now(),targets=targets,ops={},groups=[],wb_writes=0,telegram_calls=0,funding_calls=0,price_writes=0)
if old:io.put(ROOT+':execution',e)
else:assert io.create(ROOT+':execution',e)
def save():io.put(ROOT+':execution',copy.deepcopy(e))
native=requests.sessions.Session.request;allowed=None
def guard(session,method,url,*args,**kw):
 u=urlparse(url);m=method.upper();p=u.path
 if any(x in(u.hostname or'')for x in['telegram','openai']):raise PermissionError('No sends/models')
 if u.hostname=='api.moysklad.ru':assert m=='GET'and p.startswith('/api/remap/1.2/')
 if 'wildberries.ru'in(u.hostname or''):
  safe=m=='GET'and p in['/api/advert/v2/adverts','/api/advert/v1/config','/api/v2/list/goods/filter']or m=='POST'and p in['/api/advert/v1/bids/min','/api/v3/stocks/2126188']
  assert safe or allowed==(m,p,kw.get('json')),'Operation outside approval'
 return native(session,method,url,*args,**kw)
requests.sessions.Session.request=guard
def req(path,method='GET',body=None):
 time.sleep(1.2)
 r=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=(10,45))
 r.raise_for_status();return r.json()if r.content else{}
def campaign(cid):
 rows=req('/api/advert/v2/adverts?ids='+str(cid))['adverts']
 assert len(rows)==1 and rows[0]['id']==cid
 return rows[0]
def norm(c):
 d={k:copy.deepcopy(c[k])for k in['id','status','currency','settings','bid_type','nm_settings']}
 d['nm_settings']=sorted(d['nm_settings'],key=lambda x:x['nm_id']);return d
def write(key,path,body):
 global allowed
 assert key not in e['ops']
 e['ops'][key]=dict(status='submitting',path=path,body=body,submitted_at=now());save()
 allowed=('PATCH',path,body)
 try:r=req(path,'PATCH',body)
 except Exception:
  e['ops'][key]['status']='uncertain';save();raise
 finally:allowed=None
 e['wb_writes']+=1;e['ops'][key].update(status='accepted',response=r);save()
try:
 cfg=req('/api/advert/v1/config');assert cfg['currency']=='CNY'
 ids=sorted(set(x['nm']for x in targets))
 prices=current_prices(io,ids);pub=published_stock(io,prices,ids)
 pmap={x['nm_id']:x for x in prices['rows']}
 assert set(pmap)==set(ids),'Current price coverage incomplete'
 for x in targets:assert abs(pmap[x['nm']]['seller_price']-x['price'])<.001,'Price changed since reviewed plan: '+x['article']
 raisers=[x for x in targets if x['kind']=='bid'and x['target']>x['old']]
 stock=Reader().stock([x['article']for x in raisers],'msk')
 assert stock['coverage_complete']
 cur=requests.get('https://api.moysklad.ru/api/remap/1.2/entity/currency',headers={'Authorization':'Bearer '+os.environ['MOYSKLAD_API_TOKEN'],'Accept-Encoding':'gzip'},timeout=(10,45));cur.raise_for_status()
 assert next(x for x in cur.json()['rows']if x.get('default'))['isoCode']=='CNY'
 model=io.get('china_agent:advertising_full_growth:2026-11-27:v1:inputs:midday')['economics']['rows']
 econ={}
 for x in raisers:
  s=next(s for s in stock['rows']if s['article'].lower()==x['article'].lower());m=model[str(x['nm'])]
  assert s['stock']-s['reserve']>0 and pub['amounts'].get(str(x['nm']),0)>0
  profit=m['buyout']*(x['price']*(1-(m['commission_pct']+m['tax_pct']+m['payment_reserve_pct'])/100)-s['price']/100)-m['logistics_cny']-.08*x['price']
  assert profit>0,'Raise economics no longer positive: '+x['article']
  econ[str(x['nm'])]=dict(profit_at_drr8_cny=profit,cost_cny=s['price']/100,buyout=m['buyout'],stock_free=s['stock']-s['reserve'],preliminary=True)
 e['preflight']=dict(prices=prices,published=pub,raise_stock=stock,raise_economics=econ,currency='CNY',observed_at=now());save()
 # Prepare all groups before any marketplace write.
 for cid in[40933588,41270309,41298169]:
  c=campaign(cid);assert c['status']==9 and c['currency']=='CNY'and c['bid_type']=='manual'and c['settings']['payment_type']=='cpc'
  zone='search'if cid==41298169 else'recommendations';assert c['settings']['placements'][zone]
  members={n['nm_id']:n for n in c['nm_settings']};xs=[x for x in targets if x['cid']==cid]
  for x in xs:
   if x['kind']=='exclude':
    assert cid==41298169 and x['nm']==1473243444
    continue
   assert x['nm']in members
   assert members[x['nm']]['bids_kopecks'][zone]in[x['old'],x['target']],'Bid changed since reviewed plan: '+x['article']
  bidids=[x['nm']for x in xs if x['kind']=='bid']
  q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=bidids,payment_type='cpc',placement_types=['search'if zone=='search'else'recommendation']))
  mins={n['nm_id']:next(b['value']for b in n['bids']if b['type']==('search'if zone=='search'else'recommendation')and b['currency']=='CNY')for n in q['bids']}
  assert all(mins[x['nm']]<=x['target']and x['target']%cfg['cpcStep']==0 for x in xs if x['kind']=='bid')
  expected=copy.deepcopy(c)
  for n in expected['nm_settings']:
   x=next((x for x in xs if x['nm']==n['nm_id']and x['kind']=='bid'),None)
   if x:n['bids_kopecks'][zone]=x['target']
  if cid==41298169:
   expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']!=1473243444]
   assert len(expected['nm_settings'])>0 and c['restrictions']['can_change_nms']
  g=dict(cid=cid,zone=zone,before=c,expected=expected,minima={str(k):v for k,v in mins.items()},targets=xs,status='ready')
  e['groups'].append(g)
 # Ensure253 stays in the recommendation campaign.
 assert any(n['nm_id']==1473243444 and n['bids_kopecks']['recommendations']==28 for n in next(g for g in e['groups']if g['cid']==41270309)['before']['nm_settings'])
 save()
 for g in e['groups']:
  cid=g['cid'];zone=g['zone'];c=campaign(cid)
  assert norm(c)==norm(g['before']),'Concurrent campaign change; stopped before write'
  members={n['nm_id']:n for n in c['nm_settings']}
  bids=[dict(nm_id=x['nm'],bid_kopecks=x['target'],placement=zone)for x in g['targets']if x['kind']=='bid'and members[x['nm']]['bids_kopecks'][zone]!=x['target']]
  if bids:write(str(cid)+':bids','/api/advert/v1/bids',dict(bids=[dict(advert_id=cid,nm_bids=bids)]))
  if cid==41298169 and 1473243444 in members:
   # Recheck membership and other bids after accepted bid update.
   interim=copy.deepcopy(g['expected']);interim['nm_settings'] += [members[1473243444]]
   assert norm(campaign(cid))==norm(interim),'Unexpected change before exclusion'
   write(str(cid)+':exclude253','/adv/v0/auction/nms',dict(nms=[dict(advert_id=cid,nms=dict(add=[],delete=[1473243444]))]))
  for attempt in range(12):
   after=campaign(cid)
   if norm(after)==norm(g['expected']):
    time.sleep(2)
    if norm(campaign(cid))==norm(g['expected']):break
   time.sleep(2)
  else:raise ValueError('WB full state mismatch: '+str(cid))
  g.update(status='verified',after=after,verified_at=now());save()
  receipt=ROOT+':campaign:'+str(cid)
  if not io.get(receipt):assert io.create(receipt,dict(g,status='verified',parent=ROOT+':execution'))
  registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=receipt
  if io.get('china_agent:verified_campaign_state:v1'):io.put('china_agent:verified_campaign_state:v1',registry)
  else:io.create('china_agent:verified_campaign_state:v1',registry)
  for x in g['targets']:
   before=next((n for n in g['before']['nm_settings']if n['nm_id']==x['nm']),None)
   already=before is None if x['kind']=='exclude'else before['bids_kopecks'][zone]==x['target']
   x['already_done']=already
   key='china_agent:experience:v1:manual13-27-'+str(cid)+'-'+str(x['nm'])
   if not already and not io.get(key):io.create(key,dict(status='verified',started_at=g['verified_at'],execution_key=ROOT+':execution',action=dict(kind='exclusion'if x['kind']=='exclude'else'bid_change',nm_ids=[x['nm']],campaign_id=cid,before=x['old']/100,after=x['target']/100 if x['target']is not None else None)))
 final={g['cid']:campaign(g['cid'])for g in e['groups']}
 assert all(norm(final[g['cid']])==norm(g['expected'])for g in e['groups'])
 assert next(n for n in final[41270309]['nm_settings']if n['nm_id']==1473243444)['bids_kopecks']['recommendations']==28
 e.update(status='verified',verified_at=now(),final_members={str(k):len(v['nm_settings'])for k,v in final.items()},retained253_recommendations_028=True);save()
except Exception as ex:
 e.update(status='needs_reconciliation'if e['ops']else'blocked',error=type(ex).__name__+': '+str(ex)[:350]);save()
finally:requests.sessions.Session.request=native
print(json.dumps(dict(status=e['status'],error=e.get('error'),wb_writes=e['wb_writes'],groups=[dict(cid=g['cid'],status=g['status'])for g in e['groups']])))
