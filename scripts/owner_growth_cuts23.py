import os,json,time,copy,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_growth_cuts:2026-11-23:v1'
GROUPS=[(40933588,'recommendations',[(1473243911,30,28),(1473242754,30,28)],[]),(41270309,'recommendations',[(1473246049,32,28)],[]),(41325622,'search',[(1535337769,13,11)],[]),(41332083,'search',[],[1473243915])]
def now():return datetime.now(timezone.utc).isoformat()
def norm(c):return {k:sorted(c[k],key=lambda n:n['nm_id'])if k=='nm_settings'else c[k]for k in ('id','status','currency','settings','bid_type','nm_settings')}
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a and a['status']=='approved'and a['owner_id']==5122667182 and a['scope']=='four_bid_cuts_one_exclusion'
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 if io.get(ROOT+':execution'):print('Existing journal; no replay');return
 e=dict(status='preflight',groups={},wb_writes=0,telegram_calls=0,model_calls=0,created_at=now());assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',copy.deepcopy(e))
 orig=requests.sessions.Session.request;allow=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=m in ('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='advert-api.wildberries.ru':ok=(m=='GET'and u.path=='/api/advert/v2/adverts')or(m=='POST'and u.path=='/api/advert/v1/bids/min')or(allow is not None and allow==(m,u.path,kw.get('json')))
  else:ok=False
  assert ok,'Exact approved ads scope only';return orig(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def req(path,method='GET',body=None):
  time.sleep(1.3);r=requests.request(method,'https://advert-api.wildberries.ru'+path,json=body,headers={'Authorization':io.token,'Cache-Control':'no-cache,no-store'},timeout=(10,55));r.raise_for_status();return r.json()if r.content else{}
 def read(cid):
  cs=req('/api/advert/v2/adverts?ids='+str(cid)+'&owner_read='+str(time.time_ns()))['adverts'];assert len(cs)==1 and cs[0]['id']==cid;return cs[0]
 protected=read(42088552);e['protected_before']=protected;save()
 for cid,zone,bids,remove in GROUPS:
  g=dict(status='preflight',cid=cid);e['groups'][str(cid)]=g;save()
  try:
   before=read(cid);g['before']=before;assert before['currency']=='CNY'and before['status']==9;members={n['nm_id']:n for n in before['nm_settings']};expected=copy.deepcopy(before);changes=[]
   for nm,old,target in bids:
    assert nm in members and members[nm]['bids_kopecks'][zone]in (old,target),'Unreviewed current state'
    if members[nm]['bids_kopecks'][zone]!=target:changes.append(dict(nm_id=nm,bid_kopecks=target,placement=zone))
    next(n for n in expected['nm_settings']if n['nm_id']==nm)['bids_kopecks'][zone]=target
   if bids:
    typ='recommendation'if zone=='recommendations'else'search';q=req('/api/advert/v1/bids/min','POST',dict(advert_id=cid,nm_ids=[x[0]for x in bids],payment_type='cpc',placement_types=[typ]));g['minima']=q
    floors={x['nm_id']:next(b['value']for b in x['bids']if b['type']==typ and b['currency']=='CNY')for x in q['bids']};assert all(floors[nm]<=target for nm,old,target in bids),'Minimum exceeds approved bid'
   missing=sorted(set(remove)&set(members));expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']not in remove];g['expected']=expected;save()
   body={'bids':[dict(advert_id=cid,nm_bids=changes)]}if changes else {'nms':[dict(advert_id=cid,nms={'add':[],'delete':missing})]}if missing else None
   path='/api/advert/v1/bids'if changes else'/adv/v0/auction/nms'
   if body:
    g['operation']=dict(status='submitting',body=body,submitted_at=now());save();allow=('PATCH',path,body)
    try:g['operation']['response']=req(path,'PATCH',body)
    except Exception:g['operation']['status']='uncertain';save();raise
    finally:allow=None
    g['operation']['status']='accepted';e['wb_writes']+=1;save()
   streak=[]
   for _ in range(12):
    c=read(cid);g['last_read']=c;streak=streak+[c]if norm(c)==norm(expected)else[]
    if len(streak)==3:break
    time.sleep(3)
   assert len(streak)==3,'Whole-campaign verification mismatch; no retry'
   g.update(status='verified',after=c,verified_at=now(),already_done=body is None,readbacks=streak)
   if body:g['operation']['status']='verified'
   save();key=ROOT+':campaign:'+str(cid);io.create(key,dict(g,id=cid));reg=io.get('china_agent:verified_campaign_state:v1')or{};reg[str(cid)]=key;io.put('china_agent:verified_campaign_state:v1',reg)
   if body:io.create('china_agent:experience:v1:owner-growthcuts23-'+str(cid),dict(status='verified',started_at=g['verified_at'],execution_key=key,action=dict(kind='bid_change'if bids else'exclude',campaign_id=cid,nm_ids=[x[0]for x in bids]or remove),before=before,after=c))
  except Exception as ex:g.update(status='uncertain'if 'operation'in g else'blocked',error=type(ex).__name__+': '+str(ex)[:300]);save()
 # Entire package and protected campaign are checked again after all writes.
 for cid,zone,bids,remove in GROUPS:
  g=e['groups'][str(cid)]
  if g['status']=='verified':
   c=read(cid);g['package_readback']=c
   if norm(c)!=norm(g['after']):g.update(status='uncertain',error='Final package mismatch')
   io.put(ROOT+':campaign:'+str(cid),dict(g,id=cid))
 p=read(42088552);e['protected_after']=p;e['protected_unchanged']=norm(p)==norm(protected);e['status']='verified'if all(g['status']=='verified'for g in e['groups'].values())and e['protected_unchanged']else'partial_attention';e['completed_at']=now();save();print(json.dumps(dict(status=e['status'],writes=e['wb_writes'],groups=[dict(cid=g['cid'],status=g['status'],error=g.get('error'))for g in e['groups'].values()])))
if __name__=='__main__':main()