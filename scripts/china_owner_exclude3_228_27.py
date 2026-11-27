import requests,time,copy,json
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_exclude3_228_27:v1'
io=AdvertisingIO();a=io.get(ROOT+':approval')
ids=[1473245004,1473243440,1473245512];cid=42068228
assert a['status']=='approved'and a['owner_id']==5122667182 and a['campaign_id']==cid and sorted(a['nm_ids'])==sorted(ids)
def now():return datetime.now(timezone.utc).isoformat()
e=io.get(ROOT+':execution')
if e:raise SystemExit('Existing journal; never replay exclusion')
e=dict(status='preflight',created_at=now(),wb_writes=0,telegram_calls=0,price_writes=0,bid_writes=0,funding_calls=0)
assert io.create(ROOT+':execution',e)
def save():io.put(ROOT+':execution',copy.deepcopy(e))
native=requests.sessions.Session.request;allowed=None
def guard(session,method,url,*args,**kw):
 u=urlparse(url);m=method.upper()
 if any(t in(u.hostname or'')for t in['telegram','openai']):raise PermissionError('No external sends')
 if 'wildberries'in(u.hostname or''):
  assert m=='GET'and u.path=='/api/advert/v2/adverts' or allowed==(m,u.path,kw.get('json')),'Outside approved exclusion'
 return native(session,method,url,*args,**kw)
requests.sessions.Session.request=guard
def campaign(c):
 time.sleep(1)
 r=requests.get('https://advert-api.wildberries.ru/api/advert/v2/adverts',headers={'Authorization':io.token,'Cache-Control':'no-cache'},params={'ids':str(c)},timeout=(10,45));r.raise_for_status()
 rows=r.json()['adverts'];assert len(rows)==1 and rows[0]['id']==c;return rows[0]
def norm(c):
 v={k:copy.deepcopy(c[k])for k in ['id','status','currency','bid_type','settings','nm_settings']}
 v['nm_settings']=sorted(v['nm_settings'],key=lambda n:n['nm_id']);return v
try:
 before=campaign(cid)
 assert before['status']==9 and before['currency']=='CNY'and before['settings']['placements']['search']
 assert before['restrictions']['can_change_nms']
 others={c:campaign(c)for c in[41055480,41270309]}
 assert all(any(n['nm_id']==nm for n in others[c]['nm_settings'])for nm,c in[(1473245004,41055480),(1473243440,41055480),(1473245512,41270309)])
 delete=[n for n in ids if any(x['nm_id']==n for x in before['nm_settings'])]
 expected=copy.deepcopy(before);expected['nm_settings']=[x for x in expected['nm_settings']if x['nm_id']not in ids]
 assert expected['nm_settings']
 e.update(before=before,other_campaigns_before={str(k):v for k,v in others.items()},delete=delete,already_absent=sorted(set(ids)-set(delete)),expected=expected);save()
 assert norm(campaign(cid))==norm(before),'Concurrent campaign change'
 if delete:
  body=dict(nms=[dict(advert_id=cid,nms=dict(add=[],delete=delete))])
  e['operation']=dict(status='submitting',method='PATCH',path='/adv/v0/auction/nms',body=body,submitted_at=now());save()
  allowed=('PATCH','/adv/v0/auction/nms',body)
  try:
   r=requests.patch('https://advert-api.wildberries.ru/adv/v0/auction/nms',headers={'Authorization':io.token},json=body,timeout=(10,45));r.raise_for_status()
  except Exception:
   e['operation']['status']='uncertain';save();raise
  finally:allowed=None
  e['wb_writes']=1;e['operation']['status']='accepted';save()
 for _ in range(12):
  after=campaign(cid)
  if norm(after)==norm(expected):
   time.sleep(2)
   if norm(campaign(cid))==norm(expected):break
  time.sleep(2)
 else:raise ValueError('Exact full campaign readback mismatch')
 other_after={c:campaign(c)for c in others}
 assert all(norm(other_after[c])==norm(others[c])for c in others),'Other campaign changed externally'
 e.update(status='verified',after=after,other_campaigns_after={str(k):v for k,v in other_after.items()},verified_at=now());save()
 key=ROOT+':campaign:'+str(cid);assert io.create(key,dict(status='verified',before=before,after=after,verified_at=e['verified_at'],parent=ROOT+':execution'))
 registry=io.get('china_agent:verified_campaign_state:v1')or{};registry[str(cid)]=key;io.put('china_agent:verified_campaign_state:v1',registry)
 for nm in delete:
  io.create('china_agent:experience:v1:exclude3-228-27-'+str(nm),dict(status='verified',started_at=e['verified_at'],execution_key=ROOT+':execution',action=dict(kind='exclusion',nm_ids=[nm],campaign_id=cid)))
except Exception as ex:
 e.update(status='needs_reconciliation'if e.get('operation')else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save()
finally:requests.sessions.Session.request=native
print(json.dumps(dict(status=e['status'],error=e.get('error'),wb_writes=e['wb_writes'])))
