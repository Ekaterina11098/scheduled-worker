import json,time,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from owner_blocked6_clone26_apply import canonical
ROOT='china_agent:owner_deleted_one_draft26:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a['status']=='approved' and a['owner_id']==5122667182;assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at']);validate_identity(Cache(),WB())
 d=io.get(ROOT+':discovery');assert d['status']=='complete' and d['permanently_absent_candidates']==[dict(nm_id=1473244985,article='042-EvaBag-brown',draft_vendor='042-EvaBag-brown-')]
 b=next(x for x in io.get('china_agent:owner_blocked6_drafts_trash26:v1:drafts')['items'] if x['nm_id']==1473244985);body=b['draft_payload'];vendor=b['draft_vendor'];assert body[0]['variants'][0]['vendorCode']==vendor
 assert not io.get(ROOT+':execution');e=dict(status='preflight',started_at=stamp(),old_nm=b['nm_id'],article=vendor,body=body,wb_writes=0,telegram_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;allowed=False
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH') and u.path.startswith('/rest/v1/') or u.hostname=='content-api.wildberries.ru' and m=='POST' and (u.path in('/content/v2/get/cards/list','/content/v2/get/cards/trash','/content/v2/cards/error/list') or allowed and u.path=='/content/v2/cards/upload' and kw.get('json')==body);assert ok,'Only one exact recovery draft';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def post(path,data):
  r=requests.post('https://content-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=data,timeout=(10,50));r.raise_for_status();return r.json()
 def read(path,text):
  time.sleep(1);return post('/content/v2/get/cards/'+path,{'settings':{'cursor':{'limit':100},'filter':{'textSearch':text,'withPhoto':-1}}})['cards']
 def errors():return post('/content/v2/cards/error/list',{'cursor':{'limit':100},'order':{'ascending':False}})['data']['items']
 try:
  active=read('list','042-EvaBag-brown');trash=read('trash','042-EvaBag-brown');assert not any(c['nmID']==b['nm_id'] for c in active+trash),'Original still exists'
  new=[c for c in active if c['vendorCode']==vendor];assert len(new)<=1
  if not new:
   e['baseline_errors']=errors();save();assert io.get(ROOT+':approval')==a
   e['status']='submitting';save();allowed=True
   try:e['response']=post('/content/v2/cards/upload',body)
   except Exception:e['status']='uncertain';save();raise
   finally:allowed=False
   assert not e['response'].get('error'),str(e['response']);e.update(status='accepted',wb_writes=1);save()
   baseline={json.dumps(x,sort_keys=True,ensure_ascii=False) for x in e['baseline_errors']}
   for _ in range(30):
    time.sleep(5);new=[c for c in read('list',vendor) if c['vendorCode']==vendor and c['nmID']!=b['nm_id']]
    if new:break
    fresh=errors();changed=[x for x in fresh if vendor in x.get('vendorCodes',[]) and json.dumps(x,sort_keys=True,ensure_ascii=False) not in baseline]
    e['latest_errors']=fresh;save()
    if changed:e.update(status='blocked_creation_error',creation_errors=changed);save();return
  assert len(new)==1,'Card pending; no repeat POST';c=new[0];assert canonical(c)==canonical(b['before'],vendor),'Fields differ';assert not(c.get('photos') or c.get('video')),'Unexpected media'
  e.update(status='verified',after=c,new_nm=c['nmID'],verified_at=stamp());save();print(json.dumps(dict(status='verified',new_nm=c['nmID'],article=vendor)))
 except Exception as ex:
  if e['status']!='uncertain':e.update(status='attention_required',reason=type(ex).__name__+': '+str(ex)[:300]);save()
  raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

