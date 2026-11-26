import json,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_blocked6_recreate26:v1:trash_reconciliation'
def main():
 io=AdvertisingIO();assert not io.get(ROOT);out=dict(status='reading',observed_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,telegram_calls=0);assert io.create(ROOT,out)
 original=requests.sessions.Session.request
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=u.hostname==urlparse(io.url).hostname and m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')or u.hostname=='content-api.wildberries.ru'and m=='POST'and u.path in('/content/v2/get/cards/list','/content/v2/get/cards/trash');assert ok;return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 try:
  for label,path,search in [('active_nm','list','1473243449'),('trash_all','trash',''),('trash_vendor','trash','539-AdaBag-coffee')]:
   body={'settings':{'sort':{'ascending':False},'cursor':{'limit':100},'filter':{'textSearch':search,'withPhoto':-1}}};r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/'+path,headers={'Authorization':io.token},json=body,timeout=(10,50));out[label]=dict(http=r.status_code,data=r.json()if 'json'in r.headers.get('Content-Type','')else r.text[:500]);io.put(ROOT,out)
  out['status']='complete';io.put(ROOT,out)
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

