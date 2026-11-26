"""Exact owner six blocked-card rename/copy; old barcodes never modified; no media."""
import copy,json,time,requests,os
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
ROOT='china_agent:owner_blocked6_clone26:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def canonical(c,article=None):
 d={k:copy.deepcopy(c.get(k))for k in ('title','brand','description','kizMarked')};d['vendorCode']=article if article is not None else c['vendorCode'];d['subjectID']=c['subjectID'];d['dimensions']={k:c['dimensions'].get(k)for k in('length','width','height','weightBrutto')};d['characteristics']=sorted([dict(id=x['id'],value=x['value'])for x in c['characteristics']],key=lambda x:x['id']);d['sizes']=sorted([{k:x.get(k,'')for k in('techSize','wbSize','skus')}for x in c['sizes']],key=lambda x:x['techSize']);return d
def update(c,article):
 b=canonical(c,article);b.pop('subjectID');b['nmID']=c['nmID'];b['sizes']=[{k:x[k]for k in('chrtID','techSize','wbSize','skus')}for x in c['sizes']];return [b]
def upload(c,article):
 b=canonical(c,article);subject=b.pop('subjectID');return [dict(subjectID=subject,variants=[b])]
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');d=io.get(ROOT+':discovery');assert a['status']=='approved'and a['owner_id']==5122667182 and d['status']=='complete';assert set(map(int,d['cards']))==set(a['nm_ids']);validate_identity(Cache(),WB())
 def authority():assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();assert not io.get(ROOT+':execution'),'Existing operation journal retained; no replay'
 e=dict(status='preflight',started_at=stamp(),before=d['cards'],items=[],operations=[],wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;allowed=None
 def guard(session,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=False
  if u.hostname==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path in('/content/v2/get/cards/list','/content/v2/cards/error/list')or allowed is not None and (m,u.path,kw.get('json'))==allowed
  elif u.hostname=='seller-analytics-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v1/analytics/banned-products/blocked'
  assert ok,'Outside exact six card transaction';return original(session,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def read(article):
  time.sleep(.8);r=requests.post('https://content-api.wildberries.ru/content/v2/get/cards/list',headers={'Authorization':io.token,'Cache-Control':'no-cache'},json={'settings':{'cursor':{'limit':100},'filter':{'textSearch':article,'withPhoto':-1}}},timeout=(10,50));r.raise_for_status();return r.json()['cards']
 def exact(nm,article):
  found=[x for x in read(str(nm))if x['nmID']==nm];assert len(found)==1;return found[0]
 def mutate(path,body,kind,item):
  nonlocal allowed
  authority();op=dict(kind=kind,path=path,body=body,status='submitting',started_at=stamp(),nm_id=item['old_nm']);e['operations'].append(op);save();allowed=('POST',path,body)
  try:
   r=requests.post('https://content-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=(10,60));op.update(http=r.status_code,response=r.json()if r.headers.get('Content-Type','').startswith('application/json')else r.text[:1800]);op['status']='accepted'if r.ok and not(isinstance(op['response'],dict)and op['response'].get('error'))else'rejected';e['wb_writes']+=int(op['status']=='accepted');save();return op
  except Exception:op['status']='uncertain';save();raise
  finally:allowed=None
 def restored(item,before):
  op=mutate('/content/v2/cards/update',update(before,before['vendorCode']),'rollback_vendor_only',item)
  if op['status']!='accepted':return False
  for _ in range(10):
   c=exact(before['nmID'],before['vendorCode'])
   if canonical(c)==canonical(before):item.update(status='copy_rejected_original_restored',after=c,restored_at=stamp());save();return True
   time.sleep(3)
  return False
 try:
  # All original cards are durably backed up and compared before first write.
  for nm in a['nm_ids']:
   old=d['cards'][str(nm)];article=old['vendorCode'];c=exact(nm,article);assert canonical(c)==canonical(old)and not(c.get('photos')or c.get('video')),'Card changed or contains media';matches=read(article);assert not any(x['vendorCode']==article+'-'for x in matches),'Suffix already occupied';e['items'].append(dict(old_nm=nm,article=article,status='prepared',before=c));save()
  for item in e['items']:
   before=item['before'];nm=item['old_nm'];article=item['article'];fresh=exact(nm,article);assert canonical(fresh)==canonical(before),'Card changed before rename'
   op=mutate('/content/v2/cards/update',update(before,article+'-'),'rename_old_suffix',item)
   if op['status']!='accepted':e.update(status='blocked_rename_rejected');save();return
   renamed=None
   for _ in range(12):
    c=exact(nm,article)
    if canonical(c)==canonical(before,article+'-'):renamed=c;break
    time.sleep(3)
   assert renamed is not None,'Rename not verified; no copy submitted'
   item.update(status='renamed',renamed=renamed);save()
   op=mutate('/content/v2/cards/upload',upload(before,article),'copy_original_barcode_no_media',item)
   if op['status']=='rejected':
    item['copy_rejection']=op['response'];assert restored(item,before),'Rollback not verified';e.update(status='blocked_copy_rejected_original_restored',reason=op['response']);save();return
   new=None;errors=None
   for _ in range(18):
    found=[x for x in read(article)if x['vendorCode']==article and x['nmID']!=nm]
    assert len(found)<=1,'Multiple new copies; no retry'
    if found:new=found[0];break
    r=requests.post('https://content-api.wildberries.ru/content/v2/cards/error/list',headers={'Authorization':io.token},json={'cursor':{'limit':100},'order':{'ascending':False}},timeout=(10,40))
    if r.ok:
     j=r.json();e['last_error_list']=j;save();errs=j.get('data',[])if isinstance(j,dict)else[]
     if isinstance(errs,list):
      matched=[x for x in errs if article in json.dumps(x,ensure_ascii=False)]
      if matched:errors=matched;break
    time.sleep(5)
   if errors:
    item['copy_rejection']=errors;assert restored(item,before),'Rollback not verified';e.update(status='blocked_copy_rejected_original_restored',reason=errors);save();return
   assert new is not None,'Creation pending: no repeated POST or rollback on uncertainty'
   assert canonical(new)==canonical(before)and not(new.get('photos')or new.get('video')),'Copy differs from approved original'
   item.update(status='verified',new_nm=new['nmID'],after=new,verified_at=stamp());save()
  e.update(status='verified',completed_at=stamp());save();print(json.dumps(dict(status='verified',cards=len(e['items']),wb_writes=e['wb_writes'])))
 except Exception as ex:e.update(status='attention_required',reason=type(ex).__name__+': '+str(ex)[:300]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

