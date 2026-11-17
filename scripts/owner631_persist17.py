"""Owner renewed exact request to finish631; no other mutation."""
import os,json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
R='china_agent:owner631_persist:2026-11-17:v1';CID=41270309;NM=1473246045
def main():
 c=Cache();w=WB();a=c.get(R+':approval');assert a['owner_id']==5122667182 and a['status']=='approved'and a['telegram_allowed']is False and a['funding_allowed']is False
 assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 validate_identity(c,w);e=dict(status='preflight',steps={},wb_writes=0,telegram_calls=0,funding_cny=0,created_at=stamp())
 assert c.create(R+':execution',e),'Never replay existing execution'
 add=dict(nms=[dict(advert_id=CID,nms=dict(add=[NM],delete=[]))])
 bid=dict(bids=[dict(advert_id=CID,nm_bids=[dict(nm_id=NM,bid_kopecks=28,placement='recommendations')])])
 def save():c.put(R+':execution',e)
 original=requests.sessions.Session.request
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper()
  ok=(u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname and u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH'))or(u.hostname=='advert-api.wildberries.ru'and((m=='GET'and u.path=='/api/advert/v2/adverts')or(m=='PATCH'and ((u.path=='/adv/v0/auction/nms'and kw.get('json')==add)or(u.path=='/api/advert/v1/bids'and kw.get('json')==bid)))))
  assert ok,'Exact631 scope exceeded';return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:
  before=w.campaigns([CID])[str(CID)];e['before']=before;save()
  assert before['status']==9 and before['currency']=='CNY'and before['settings']['placements']==dict(search=False,recommendations=True)
  for name,path,body in [('add','/adv/v0/auction/nms',add),('bid','/api/advert/v1/bids',bid)]:
   e['steps'][name]=dict(status='submitting',request=body,submitted_at=stamp());save()
   r=requests.patch('https://advert-api.wildberries.ru'+path,headers={'Authorization':w.token},json=body,timeout=55)
   e['steps'][name].update(status='accepted'if r.ok else'rejected',http_status=r.status_code,response=r.text[:2000],answered_at=stamp());e['wb_writes']+=int(r.ok);save()
   if not r.ok:
    if name=='add'and r.status_code==400 and ('already'in r.text.lower()or 'belong'in r.text.lower()):pass
    else:raise RuntimeError('WB refused '+name+': '+str(r.status_code)+' '+r.text[:700])
   time.sleep(3)
  reads=[]
  for j in range(2):
   reads.append(w.campaigns([CID])[str(CID)]);time.sleep(4)
  e['reads']=reads
  valid=all(any(n['nm_id']==NM and n['bids_kopecks']['recommendations']==28 for n in x['nm_settings'])and not any(n['nm_id']==1604165742 for n in x['nm_settings'])for x in reads)
  e.update(status='verified'if valid else'needs_ui_verification',after=reads[-1],checked_at=stamp());save()
  print(json.dumps(dict(status=e['status'],steps=e['steps'],targets=[[n for n in x['nm_settings']if n['nm_id']in(NM,1604165742)]for x in reads])))
 except Exception as ex:
  e.update(status='uncertain'if any(v['status']=='submitting'for v in e['steps'].values())else'blocked',reason=str(ex)[:900]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
