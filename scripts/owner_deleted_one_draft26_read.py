import json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_deleted_one_draft26:v1'
def main():
 io=AdvertisingIO();assert not io.get(ROOT+':discovery');backup=io.get('china_agent:owner_blocked6_drafts_trash26:v1:drafts');assert len(backup['items'])==6;bm={i['nm_id']:i for i in backup['items']};names={i['article']for i in bm.values()}|{i['draft_vendor']for i in bm.values()};out=dict(status='reading',observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0);assert io.create(ROOT+':discovery',out)
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')or u.hostname=='content-api.wildberries.ru'and m=='POST'and u.path in('/content/v2/get/cards/list','/content/v2/get/cards/trash','/content/v2/cards/error/list');assert ok,'Read only';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:
  allids={}
  for label,path in [('active','list'),('trash','trash')]:
   cur={'limit':100};found=[];ids=[];complete=False
   for page in range(20):
    time.sleep(.8);body={'settings':{'sort':{'ascending':False},'cursor':cur,'filter':{'withPhoto':-1}}};r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=(10,50));r.raise_for_status();j=r.json();rows=j['cards'];ids +=[c['nmID']for c in rows];found +=[c for c in rows if c['nmID']in bm or c['vendorCode']in names];cursor=j['cursor']
    if len(rows)<100:complete=True;break
    cur={**{k:v for k,v in cursor.items()if k!='total'},'limit':100}
   assert complete and len(ids)==len(set(ids)),'Inventory incomplete';allids[label]=set(ids);out[label]=dict(cards=found,total=len(ids),coverage_complete=True);io.put(ROOT+':discovery',out)
  missing=[dict(nm_id=n,article=bm[n]['article'],draft_vendor=bm[n]['draft_vendor'])for n in bm if n not in allids['active']and n not in allids['trash']];out['permanently_absent_candidates']=missing
  r=requests.post('https://content-api.wildberries.ru/content/v2/cards/error/list',headers={'Authorization':io.token},json={'cursor':{'limit':100},'order':{'ascending':False}},timeout=(10,40));r.raise_for_status();out['error_drafts']=r.json();out['status']='complete';io.put(ROOT+':discovery',out);print(json.dumps(dict(status='complete',candidates=missing,active=out['active']['total'],trash=out['trash']['total'])))
 except Exception as ex:out.update(status='blocked',reason=type(ex).__name__+': '+str(ex)[:250]);io.put(ROOT+':discovery',out);raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

