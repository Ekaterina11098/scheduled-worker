"""Create six suffix copies only; exact original barcodes; no original updates."""
import copy,json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from owner_blocked6_clone26_apply import canonical,upload
ROOT='china_agent:owner_blocked6_suffixcopy26:v1'
SOURCE='china_agent:owner_blocked6_clone26:v1:discovery'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');d=io.get(SOURCE);assert a['status']=='approved'and a['owner_id']==5122667182 and d['status']=='complete';assert set(map(int,d['cards']))==set(a['nm_ids']);validate_identity(Cache(),WB())
 def authority():assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();assert not io.get(ROOT+':execution'),'Existing journal retained; no repeated creation'
 e=dict(status='preflight',started_at=stamp(),items=[],operations=[],wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=False
  if u.hostname==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path in('/content/v2/get/cards/list','/content/v2/cards/error/list')or m=='GET'and u.path=='/content/v2/cards/error/list'or allowed is not None and(m,u.path,kw.get('json'))==allowed
  assert ok,'Only exact suffix copies; no update/media/delete endpoints';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def read(text):
  time.sleep(.8);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token,'Cache-Control':'no-cache'},json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':text,'withPhoto':-1}}},timeout=(10,50));r.raise_for_status();return r.json()['cards']
 def errors():
  path='https://content-api.wildberries.ru/content/v2/cards/error/list';h={'Authorization':io.token};r=requests.post(path,headers=h,json={'cursor':{'limit':100},'order':{'ascending':False}},timeout=(10,40))
  if r.status_code in(404,405):r=requests.get(path,headers=h,params={'limit':100,'offset':0},timeout=(10,40))
  return dict(http=r.status_code,response=r.json()if 'json'in r.headers.get('Content-Type','')else r.text[:1000])
 try:
  for nm in a['nm_ids']:
   old=d['cards'][str(nm)];rows=read(str(nm));found=[x for x in rows if x['nmID']==nm];assert len(found)==1;before=found[0];assert canonical(before)==canonical(old),'Source changed since backup'
   name=before['vendorCode']+'-';matches=[x for x in read(name)if x['vendorCode']==name];assert len(matches)<=1
   item=dict(old_nm=nm,article=before['vendorCode'],new_article=name,before=before,status='already_exists'if matches else'prepared')
   if matches:assert canonical(matches[0])==canonical(before,name)and not(matches[0].get('photos')or matches[0].get('video')),'Existing suffix card is different';item.update(new_nm=matches[0]['nmID'],after=matches[0])
   e['items'].append(item);save()
  baseline=errors();e['baseline_error_list']=baseline;save()
  for item in e['items']:
   if item['status']=='already_exists':continue
   before=item['before'];nm=item['old_nm'];name=item['new_article'];fresh=[x for x in read(str(nm))if x['nmID']==nm];assert len(fresh)==1 and canonical(fresh[0])==canonical(before),'Original changed'
   body=upload(before,name);authority();assert not any(o['old_nm']==nm for o in e['operations']);op=dict(old_nm=nm,status='submitting',body=body,started_at=stamp());e['operations'].append(op);save();allowed=('POST','/content/v2/cards/upload',body)
   try:
    r=requests.post('https://content-api.wildberries.ru/content/v2/cards/upload',headers={'Authorization':io.token},json=body,timeout=(10,60));op.update(http=r.status_code,response=r.json()if 'json'in r.headers.get('Content-Type','')else r.text[:2000]);op['status']='accepted'if r.ok and not(isinstance(op['response'],dict)and op['response'].get('error'))else'rejected';save()
   except Exception:op.update(status='uncertain');save();raise
   finally:allowed=None
   if op['status']=='rejected':item['status']='rejected';e.update(status='blocked_creation_rejected',reason=op['response']);save();return
   e['wb_writes']+=1;item['status']='submitted';save();new=None
   for _ in range(24):
    found=[x for x in read(name)if x['vendorCode']==name and x['nmID']!=nm];assert len(found)<=1,'Multiple suffix copies; no repeated POST'
    if found:new=found[0];break
    err=errors();item['last_error_list']=err;save();data=err['response'].get('data',[])if isinstance(err['response'],dict)else[]
    if isinstance(data,list):
     matches=[x for x in data if name in json.dumps(x,ensure_ascii=False)]
     if matches:item.update(status='rejected',creation_errors=matches);e.update(status='blocked_creation_error',reason=matches);save();return
    time.sleep(5)
   assert new is not None,'Creation pending; do not repeat request'
   assert canonical(new)==canonical(before,name)and not(new.get('photos')or new.get('video')),'Copy fields differ'
   original_after=[x for x in read(str(nm))if x['nmID']==nm];assert len(original_after)==1 and canonical(original_after[0])==canonical(before),'Original changed'
   item.update(status='verified',new_nm=new['nmID'],after=new,original_after=original_after[0],verified_at=stamp());save()
  e.update(status='verified',completed_at=stamp());save();print(json.dumps(dict(status='verified',cards=len(e['items']),wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:e.update(status='attention_required',reason=type(ex).__name__+': '+str(ex)[:300]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

