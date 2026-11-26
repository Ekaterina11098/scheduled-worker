"""Owner six recovery drafts + move originals to trash; no barcode removal/recovery."""
import json,copy,time,os,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from owner_blocked6_clone26_apply import canonical,upload
from owner_blocked6_suffixcopy26 import creation_errors
from owner_blocked6_recreate26 import trash_matches
ROOT='china_agent:owner_blocked6_drafts_trash26:v1'
def stamp():return datetime.now(timezone.utc).isoformat()
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');assert a['status']=='approved'and a['owner_id']==5122667182 and len(a['nm_ids'])==6;backup=io.get('china_agent:owner_blocked6_recreate26:v1:backup');assert backup['status']=='complete';bm={x['old_nm']:x['before']for x in backup['items']};assert set(a['nm_ids'])==set(bm);validate_identity(Cache(),WB())
 def authority():assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();assert not io.get(ROOT+':execution'),'Existing journal retained; no blind replay'
 e=dict(status='preflight',started_at=stamp(),items=[],operations=[],wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=False
  if u.hostname==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path in('/content/v2/get/cards/list','/content/v2/get/cards/trash','/content/v2/cards/error/list')or allowed is not None and(m,u.path,kw.get('json'))==allowed
  assert ok,'Only recovery draft creation and exact original soft deletion allowed';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def call(path,body):
  time.sleep(.8);r=requests.post('https://content-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=(10,50));r.raise_for_status();return r.json()
 def read(text,trash=False):return call('/content/v2/get/cards/trash'if trash else'/content/v2/get/cards/list',{'settings':{'sort':{'ascending':False},'cursor':{'limit':100},'filter':{'textSearch':text,'withPhoto':-1}}})['cards']
 def mutate(path,body,kind):
  nonlocal allowed
  authority();assert not any(x['kind']==kind for x in e['operations']),'No repeated mutation';op=dict(kind=kind,path=path,body=body,status='submitting',started_at=stamp());e['operations'].append(op);save();allowed=('POST',path,body)
  try:
   r=requests.post('https://content-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=(10,60));op.update(http=r.status_code,response=r.json()if 'json'in r.headers.get('Content-Type','')else r.text[:2000]);op['status']='accepted'if r.ok and not(isinstance(op['response'],dict)and op['response'].get('error'))else'rejected';e['wb_writes']+=int(op['status']=='accepted');save();return op
  except Exception:op['status']='uncertain';save();raise
  finally:allowed=None
 try:
  for nm in a['nm_ids']:
   active=[x for x in read(str(nm))if x['nmID']==nm];assert len(active)<=1
   if active:before=active[0];assert canonical(before)==canonical(bm[nm]),'Original changed; preserve new owner edits'
   else:
    removed=[x for x in read(bm[nm]['vendorCode'],True)if x['nmID']==nm];assert len(removed)==1 and trash_matches(removed[0],bm[nm]);before=bm[nm]
   e['items'].append(dict(nm_id=nm,article=before['vendorCode'],before=before,was_active=bool(active),draft_vendor=before['vendorCode']+'-',restore_payload=upload(before,before['vendorCode']),draft_payload=upload(before,before['vendorCode']+'-'),draft_status='prepared'));save()
  drafts=dict(status='prepared',created_at=stamp(),items=copy.deepcopy(e['items']),source_backup_key='china_agent:owner_blocked6_recreate26:v1:backup',photos=[],video=None,keep_original_barcodes=True);assert io.create(ROOT+':drafts',drafts);assert io.get(ROOT+':drafts')==drafts;e['drafts_backup_verified']=True;save()
  err=call('/content/v2/cards/error/list',{'cursor':{'limit':100},'order':{'ascending':False}});e['baseline_error_list']=err;save();to_upload=[]
  for item in e['items']:
   matches=creation_errors(err,item['draft_vendor'])
   if matches:item.update(draft_status='existing_WB_error_draft',draft_errors=matches);save()
   else:
    existing=[x for x in read(item['draft_vendor'])if x['vendorCode']==item['draft_vendor']]
    assert len(existing)<=1
    if existing:assert canonical(existing[0])==canonical(item['before'],item['draft_vendor']);item.update(draft_status='existing_card_no_media',draft_nm=existing[0]['nmID']);save()
    else:to_upload+=item['draft_payload']
  if to_upload:
   op=mutate('/content/v2/cards/upload',to_upload,'create_missing_recovery_drafts')
   e['draft_request_status']=op['status'];save()
   if op['status']=='accepted':
    names={item['draft_vendor']for item in e['items']if item['draft_status']=='prepared'}
    for _ in range(18):
     err=call('/content/v2/cards/error/list',{'cursor':{'limit':100},'order':{'ascending':False}});e['last_error_list']=err
     for item in e['items']:
      if item['draft_vendor']not in names or item['draft_status']!='prepared':continue
      matches=creation_errors(err,item['draft_vendor'])
      if matches:item.update(draft_status='WB_error_draft',draft_errors=matches)
     save()
     if all(item['draft_status']!='prepared'for item in e['items']):break
     time.sleep(5)
  # Draft storage is distinct from publication; duplicate barcode errors are expected.
  e['status']='drafts_prepared';save();active_ids=[]
  for item in e['items']:
   active=[x for x in read(str(item['nm_id']))if x['nmID']==item['nm_id']]
   if active:assert len(active)==1 and canonical(active[0])==canonical(item['before']);active_ids.append(item['nm_id'])
  if active_ids:e['trash_response']=mutate('/content/v2/cards/delete/trash',{'nmIDs':active_ids},'move_originals_to_trash');save()
  for item in e['items']:
   for _ in range(12):
    active=[x for x in read(str(item['nm_id']))if x['nmID']==item['nm_id']];removed=[x for x in read(item['article'],True)if x['nmID']==item['nm_id']]
    if not active and len(removed)==1 and trash_matches(removed[0],item['before']):item.update(status='verified_in_trash',trash_readback=removed[0],verified_at=stamp());save();break
    time.sleep(3)
   else:item.update(status='trash_not_verified',active_readback=active,trash_readback=removed);save()
  count=sum(x.get('status')=='verified_in_trash'for x in e['items']);e.update(status='verified'if count==6 else'partial',trash_count=count,wb_error_draft_count=sum(x['draft_status']in('WB_error_draft','existing_WB_error_draft')for x in e['items']),completed_at=stamp());save();print(json.dumps(dict(status=e['status'],trash_count=count,wb_error_draft_count=e['wb_error_draft_count'],draft_backups=6,wb_writes=e['wb_writes'],telegram_calls=0)))
 except Exception as ex:e.update(status='attention_required',reason=type(ex).__name__+': '+str(ex)[:350]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

