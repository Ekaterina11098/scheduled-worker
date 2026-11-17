"""Explicit owner recovery: keep631 at28, exclude016 only. No Telegram/funding."""
import os,json,time,copy
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_package_readback import validate
ROOT='china_agent:owner_016_exclude631_keep:2026-11-17:v1'
CID=41270309;KEEP=1473246045;REMOVE=1604165742
def main():
 c=Cache();w=WB();a=c.get(ROOT+':approval')
 assert a['status']=='approved'and a['owner_id']==5122667182 and a['campaign_id']==CID and a['keep_nm']==KEEP and a['exclude_nm']==REMOVE and a['keep_bid_minor']==28
 assert a['telegram_allowed']is False and a['funding_allowed']is False
 def authority():assert c.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();validate_identity(c,w)
 assert not c.get(ROOT+':execution'),'Existing execution: reconcile read-only, never replay'
 e=dict(status='preflight',approval_key=ROOT+':approval',items=[],wb_writes=0,funding_cny=0,telegram_calls=0,stock_writes=0,model_calls=0,created_at=stamp())
 assert c.create(ROOT+':execution',e)
 def save():c.put(ROOT+':execution',e)
 original=requests.sessions.Session.request
 body=dict(nms=[dict(advert_id=CID,nms=dict(add=[],delete=[REMOVE]))])
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path=='/api/advert/v2/adverts' or m=='PATCH'and u.path=='/adv/v0/auction/nms'and kw.get('json')==body
  else:ok=False
  assert ok,'Outside exact owner scope'
  return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def read(cid=CID):return w.campaigns([cid])[str(cid)]
 try:
  before=read();e['before']=before;save();by={n['nm_id']:n for n in before['nm_settings']}
  assert before['status']==9 and before['currency']=='CNY'and before['settings']['placements']==dict(search=False,recommendations=True)
  assert KEEP in by and by[KEEP]['bids_kopecks']['recommendations']==28,'631 not present at approved28; no automatic restore or other write'
  item=dict(id=str(CID)+':exclude:'+str(REMOVE),kind='ad_exclude_sku',campaign_id=CID,nm_id=REMOVE,placement='recommendations',old_minor=28)
  state=dict(id=item['id'],status='preflight',before=before);e['items']=[state];save()
  if REMOVE in by:
   authority();assert read()['nm_settings']==before['nm_settings'],'Composition changed before submission'
   state.update(status='submitting',request=body,submitted_at=stamp());save()
   state['response']=w.req('/adv/v0/auction/nms','PATCH',body,write=True);e['wb_writes']=1;state['status']='accepted';save()
   for attempt in range(8):
    after=read()
    if not any(n['nm_id']==REMOVE for n in after['nm_settings']):break
    if attempt==7:raise RuntimeError('016 remains; no blind retry')
    time.sleep(5)
   state.update(status='verified',after=after,verified_at=stamp());save()
  else:state.update(status='verified',already_absent=True,after=before,verified_at=stamp());save()
  e['package_readback']=validate([item],e['items'],read);save()
  assert e['package_readback']['status']=='verified','Whole package failed final verification'
  after=e['package_readback']['rounds'][-1]['campaigns'][str(CID)]
  assert any(n['nm_id']==KEEP and n['bids_kopecks']['recommendations']==28 for n in after['nm_settings'])
  e.update(status='verified',after=after,verified_at=stamp(),keep631_preserved=True);save()
  registry=c.get('china_agent:verified_campaign_state:v1')or{};registry[str(CID)]=ROOT+':execution';c.put('china_agent:verified_campaign_state:v1',registry)
  c.put('china_agent:ad_rule_execution:owner016-exclude631-keep17:v1',dict(status='done',canonical_source_execution_key=ROOT+':execution',alias_of_verified_batch=True,wb_writes=0,items=[dict(item,status='verified',before=before,after=after,verified_at=e['verified_at'],source_execution_key=ROOT+':execution')]))
  e['reporting_registered']=True;save()
  print(json.dumps(dict(status=e['status'],keep631_bid_cny=.28,excluded016=True,wb_writes=e['wb_writes'],funding_cny=0,telegram_calls=0,package_rounds=len(e['package_readback']['rounds']))))
 except Exception as ex:
  e.update(status='uncertain'if any(s['status']in('submitting','accepted','verified','uncertain')for s in e['items'])else'blocked',reason=type(ex).__name__+': '+str(ex)[:200]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

