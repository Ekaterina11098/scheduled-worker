"""Exact six backups and reversible trash/recreate pilot. No hard delete/new barcodes/media."""
import json,time,copy,os,requests
from datetime import datetime,timezone
from urllib.parse import urlparse
from china_advertising_state import AdvertisingIO
from china_cloud_cost_control import Cache,WB,validate_identity
from owner_blocked6_clone26_apply import canonical,upload
from owner_blocked6_suffixcopy26 import creation_errors
ROOT='china_agent:owner_blocked6_recreate26:v1'
SOURCE='china_agent:owner_blocked6_clone26:v1:discovery'
def stamp():return datetime.now(timezone.utc).isoformat()
def trash_matches(trash,before):
 # Trash API omits title/brand/description/kizMarked; absence is not field deletion.
 if trash.get('nmID')!=before['nmID']or trash.get('vendorCode')!=before['vendorCode']:return False
 def chars(c):return sorted([dict(id=x['id'],value=x['value'])for x in c.get('characteristics',[])],key=lambda x:x['id'])
 def sizes(c):return sorted(c.get('sizes',[]),key=lambda x:x.get('chrtID',0))
 return chars(trash)==chars(before)and sizes(trash)==sizes(before)and trash.get('dimensions')==before.get('dimensions')
def main():
 io=AdvertisingIO();a=io.get(ROOT+':approval');d=io.get(SOURCE);assert a['status']=='approved'and a['owner_id']==5122667182 and d['status']=='complete';assert set(a['nm_ids'])==set(map(int,d['cards']));validate_identity(Cache(),WB())
 def authority():assert io.get(ROOT+':approval')==a and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_at'])
 authority();assert not io.get(ROOT+':execution'),'Existing journal: no replay'
 e=dict(status='backup',started_at=stamp(),items=[],operations=[],wb_writes=0,telegram_calls=0,model_calls=0);assert io.create(ROOT+':execution',e)
 def save():io.put(ROOT+':execution',json.loads(json.dumps(e)))
 original=requests.sessions.Session.request;allowed=None
 def guard(s,method,url,*args,**kw):
  u=urlparse(url);m=method.upper();ok=False
  if u.hostname==urlparse(io.url).hostname:ok=m in('GET','POST','PATCH')and u.path.startswith('/rest/v1/')
  elif u.hostname=='content-api.wildberries.ru':ok=m=='POST'and u.path in('/content/v2/get/cards/list','/content/v2/get/cards/trash','/content/v2/cards/error/list')or allowed is not None and(m,u.path,kw.get('json'))==allowed
  elif u.hostname=='discounts-prices-api.wildberries.ru':ok=m=='GET'and u.path=='/api/v2/list/goods/filter'
  assert ok,'Outside backup/trash/recreate scope';return original(s,method,url,*args,**kw)
 requests.sessions.Session.request=guard
 def call(path,body):
  time.sleep(.8);r=requests.post('https://content-api.wildberries.ru'+path,headers={'Authorization':io.token,'Cache-Control':'no-cache'},json=body,timeout=(10,50));r.raise_for_status();return r.json()
 def read(text,trash=False):
  j=call('/content/v2/get/cards/trash'if trash else'/content/v2/get/cards/list',{'settings':{'sort':{'ascending':False},'cursor':{'limit':100},'filter':{'textSearch':text,'withPhoto':-1}}});assert isinstance(j.get('cards'),list),'Card list schema';return j['cards']
 def exact(nm,trash=False):return [x for x in read(d['cards'][str(nm)]['vendorCode']if trash else str(nm),trash)if x['nmID']==nm]
 def mutate(path,body,kind,item):
  nonlocal allowed
  authority();assert not any(x['kind']==kind and x['old_nm']==item['old_nm']for x in e['operations']),'Operation replay blocked';op=dict(kind=kind,old_nm=item['old_nm'],body=body,status='submitting',started_at=stamp());e['operations'].append(op);save();allowed=('POST',path,body)
  try:
   r=requests.post('https://content-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=(10,60));op.update(http=r.status_code,response=r.json()if 'json'in r.headers.get('Content-Type','')else r.text[:2000]);op['status']='accepted'if r.ok and not(isinstance(op['response'],dict)and op['response'].get('error'))else'rejected';e['wb_writes']+=int(op['status']=='accepted');save();return op
  except Exception:op.update(status='uncertain');save();raise
  finally:allowed=None
 def restore(item):
  op=mutate('/content/v2/cards/recover',{'nmIDs':[item['old_nm']]},'restore_original',item)
  if op['status']!='accepted':return False
  for _ in range(16):
   found=exact(item['old_nm'])
   if len(found)==1 and canonical(found[0])==canonical(item['before']):item.update(status='restored_original',after_restore=found[0],restored_at=stamp());save();return True
   time.sleep(3)
  return False
 try:
  # Restore endpoint and trash-list schema must be known before moving anything.
  e['trash_inventory_preflight']=read('',True);save()
  for nm in a['nm_ids']:
   found=exact(nm);assert len(found)==1;before=found[0];assert canonical(before)==canonical(d['cards'][str(nm)]),'Source changed';assert not(before.get('photos')or before.get('video'))
   e['items'].append(dict(old_nm=nm,article=before['vendorCode'],before=before,status='backed_up'));save()
  r=requests.get('https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter',params={'limit':1000,'offset':0},headers={'Authorization':io.token},timeout=(10,45));r.raise_for_status();goods=r.json()['data']['listGoods'];assert len(goods)<1000;e['prices_backup']=[x for x in goods if x['nmID']in a['nm_ids']];save()
  assert io.create(ROOT+':backup',dict(status='complete',items=e['items'],prices=e['prices_backup'],source_key=SOURCE,created_at=stamp()));e['backup_verified']=io.get(ROOT+':backup')['items']==e['items'];assert e['backup_verified'];save()
  for item in e['items']:
   nm=item['old_nm'];article=item['article'];fresh=exact(nm);assert len(fresh)==1 and canonical(fresh[0])==canonical(item['before'])
   op=mutate('/content/v2/cards/delete/trash',{'nmIDs':[nm]},'move_original_to_trash',item)
   if op['status']!='accepted':e.update(status='blocked_delete_rejected',reason=op['response']);save();return
   trashed=False
   for _ in range(12):
    active=exact(nm);removed=exact(nm,True)
    if not active and len(removed)==1 and trash_matches(removed[0],item['before']):item.update(status='in_trash',trash_readback=removed[0]);trashed=True;save();break
    time.sleep(3)
   if not trashed:
    # Accepted trash request with unchanged active card is a no-op, never repeat it.
    active=exact(nm)
    if len(active)==1 and canonical(active[0])==canonical(item['before']):e.update(status='blocked_delete_not_effective',reason='WB accepted trash request but exact original stayed active');save();return
    raise ValueError('Trash outcome unknown; do not repeat')
   if a.get('manual_permanent_delete_handoff'):
    e.update(status='awaiting_owner_permanent_delete',handoff_nm=nm,handoff_article=article,backup_key=ROOT+':backup',handoff_at=stamp());save();return
   op=mutate('/content/v2/cards/upload',upload(item['before'],article),'create_replacement_same_barcode',item)
   rejection=op['response']if op['status']=='rejected'else None;new=None
   if rejection is None:
    for _ in range(24):
     found=[x for x in read(article)if x['vendorCode']==article and x['nmID']!=nm];assert len(found)<=1
     if found:new=found[0];break
     j=call('/content/v2/cards/error/list',{'cursor':{'limit':100},'order':{'ascending':False}});item['last_errors']=j;save();matched=creation_errors(j,article)
     if matched:rejection=matched;break
     time.sleep(5)
   if rejection is not None:
    item['replacement_rejection']=rejection;save();assert restore(item),'Original recovery not verified';e.update(status='blocked_recreate_rejected_original_restored',reason=rejection);save();return
   assert new is not None,'Replacement pending; neither repeated creation nor hard delete allowed'
   assert canonical(new)==canonical(item['before'])and not(new.get('photos')or new.get('video')),'Replacement differs from source'
   item.update(status='verified_recreated',new_nm=new['nmID'],after=new,verified_at=stamp());save()
  e.update(status='verified',completed_at=stamp());save()
 except Exception as ex:e.update(status='attention_required',reason=type(ex).__name__+': '+str(ex)[:350]);save();raise
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()

