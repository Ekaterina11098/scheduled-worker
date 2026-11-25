"""Owner-authorized versioned report amendment. Edit existing photos only; no WB/model access."""
import base64,datetime,hashlib,json,os,tempfile
from pathlib import Path
import requests
from china_codex_cloud import DB as BaseDB,stamp
from ooo_report_command import digest,approve
import ooo_daily_reports as reports
ROOT='ooo_agent:report_replace:2026-11-25:v2'
COMMAND='ooo_agent:sol_dialog:v1:'
class DB(BaseDB):
 def once(self,k,v):
  rows=self.api('POST','telegram_api_cache',body={'cache_key':k,'payload':v,'updated_at':stamp(),'expires_at':'2027-11-25T00:00:00Z'})
  if len(rows)!=1 or self.get(k)!=v:raise RuntimeError('Atomic private claim failed')

def run():
 db=DB();auth=db.get(ROOT+':authorization')or{}
 if auth.get('status')!='approved'or auth.get('operation')!='replace_photos_and_rebind_only':raise PermissionError('Exact owner amendment authorization required')
 chat=auth['chat_id'];bot=auth['bot_id'];day=auth['day'];plan_id=auth['new_plan_id']
 if chat!=-1003987998401 or bot!=9167526388 or day!='2026-11-25':raise PermissionError('Scope mismatch')
 if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(auth['expires_at']):raise PermissionError('Edit authorization expired')
 group=db.get('ooo_agent:telegram_group:v1')or{}
 if group.get('status')!='verified'or group.get('chat_id')!=chat:raise PermissionError('Group identity mismatch')
 old_key=COMMAND+'publication:'+auth['old_plan_id'];new_key=COMMAND+'publication:'+plan_id
 old=db.get(old_key)or{}
 if old.get('manifest_sha256')!=auth['old_manifest_sha256']:raise PermissionError('Original publication changed')
 def no_prior_execution():
  if db.get(COMMAND+'approved_report:'+auth['old_plan_id'])or db.get(COMMAND+'approved_report:'+plan_id):raise PermissionError('Existing approval prevents replacement')
 s=db.get(ROOT+':execution')
 if s and s.get('status')=='verified':print('Already replaced and bound; no repeat');return
 no_prior_execution()
 if not s:s={'status':'preparing','started_at':stamp(),'edits':{},'new_messages':0,'wb_writes':0,'model_calls':0};db.once(ROOT+':execution',s)
 def save():
  if not db.update(ROOT+':execution',s):raise RuntimeError('Receipt persistence failed')
 try:
  images=[];review=None
  original_execute=reports.execute
  def capture(code,path):
   nonlocal review
   result=original_execute(code,path)
   if path.name=='render.py':
    review=json.loads((path.parent/'ooo_morning12_review.json').read_text())
    for kind in ('advertising','budgets'):
     raw=(path.parent.parent/'outputs'/('VESCHI_OOO_'+kind+'_'+day+'_actions_only.png')).read_bytes()
     images.append({'kind':kind,'raw':raw,'sha256':hashlib.sha256(raw).hexdigest()})
   return result
  reports.execute=capture
  try:reports.worker('morning',day=day,verify=True)
  finally:reports.execute=original_execute
  if review is None or len(images)!=2:raise RuntimeError('Complete render required')
  manifest={'cabinet':'token_1','currency':'KGS','actions':[{k:v for k,v in x.items()if k!='article'}for x in review['actions']],'topups':review['funding'],'other_changes':[]}
  if manifest!=auth['manifest']or digest(manifest)!=auth['manifest_sha256']:raise PermissionError('Rendered actions differ from exact authorized amendment')
  receipts=[ROOT+':delivery:'+x['kind']for x in images]
  publication={'status':'prepared','plan_id':plan_id,'chat_id':chat,'manifest':manifest,'manifest_sha256':digest(manifest),'expires_at':auth['publication_expires_at'],'artifact_sha256':[x['sha256']for x in images],'receipt_keys':receipts,'supersedes':auth['old_plan_id'],'amendment_authorization':ROOT+':authorization'}
  prior=db.get(new_key)
  if prior and any(prior.get(k)!=publication[k]for k in ('manifest','manifest_sha256','artifact_sha256','receipt_keys')):raise PermissionError('New frozen publication changed')
  if not prior:db.once(new_key,publication)
  no_prior_execution()
  for kind,mid in auth['message_ids'].items():
   key=COMMAND+'report_binding:'+str(chat)+':'+str(mid)
   b=db.get(key)or{};history=ROOT+':old_binding:'+str(mid)
   if not db.get(history):
    if b.get('plan_id')!=auth['old_plan_id']or b.get('manifest_sha256')!=auth['old_manifest_sha256']:raise PermissionError('Original message binding mismatch')
    db.once(history,b)
   if b.get('plan_id')==plan_id:continue
   b.update(status='superseded',superseded_by=plan_id,amendment_key=ROOT+':authorization');db.update(key,b)
  url='https://api.telegram.org/bot'+os.environ['OOO_TELEGRAM_BOT_TOKEN']
  me=requests.post(url+'/getMe',timeout=(10,30),allow_redirects=False)
  if me.status_code!=200 or me.json().get('result',{}).get('id')!=bot:raise PermissionError('Bot identity mismatch')
  for image in images:
   kind=image['kind'];mid=auth['message_ids'][kind];key=ROOT+':delivery:'+kind
   previous=db.get(key)
   if previous:
    if previous.get('status')=='verified'and previous.get('sha256')==image['sha256']:continue
    raise RuntimeError('Prior edit outcome retained; no replay')
   original=db.get('ooo_agent:morning:'+day+':telegram:delivery:'+kind)or{}
   if original.get('status')not in('sent','verified')or original.get('chat_id')!=chat or original.get('message_id')!=mid:raise PermissionError('Original photo receipt mismatch')
   if db.get(ROOT+':authorization')!=auth:raise PermissionError('Authorization changed')
   if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(auth['expires_at']):raise PermissionError('Edit authorization expired')
   receipt={'status':'submitting','chat_id':chat,'message_id':mid,'sha256':image['sha256'],'submitted_at':stamp()};db.once(key,receipt)
   if original['sha256']==image['sha256']:
    receipt.update(status='verified',operation='retain_identical_verified_photo',original_receipt='ooo_agent:morning:'+day+':telegram:delivery:'+kind,verified_at=stamp());db.update(key,receipt);continue
   try:
    response=requests.post(url+'/editMessageMedia',data={'chat_id':str(chat),'message_id':str(mid),'media':json.dumps({'type':'photo','media':'attach://photo'})},files={'photo':(kind+'.png',image['raw'],'image/png')},timeout=(10,60),allow_redirects=False)
   except requests.RequestException:
    receipt.update(status='uncertain');db.update(key,receipt);raise RuntimeError('Unknown edit result; no repeat')from None
   try:body=response.json()
   except ValueError:body={}
   result=body.get('result',{})
   if response.status_code!=200 or not body.get('ok')or result.get('message_id')!=mid or result.get('chat',{}).get('id')!=chat or result.get('from',{}).get('id')!=bot:
    receipt.update(status='uncertain'if response.status_code==200 else'rejected',http_status=response.status_code,description=body.get('description'));db.update(key,receipt);raise RuntimeError('Photo edit not verified')
   receipt.update(status='verified',operation='editMessageMedia',verified_at=stamp());db.update(key,receipt)
  no_prior_execution()
  # Explicit owner-authorized replacement; ordinary bind_delivery remains immutable.
  for key in receipts:
   receipt=db.get(key)
   if receipt.get('status')!='verified'or receipt['sha256']not in publication['artifact_sha256']:raise RuntimeError('Independent edited-photo receipt missing')
   bind_key=COMMAND+'report_binding:'+str(chat)+':'+str(receipt['message_id'])
   current=db.get(bind_key)or{}
   if current.get('plan_id')==plan_id:continue
   if current.get('status')!='superseded'or current.get('superseded_by')!=plan_id:raise PermissionError('Binding not locked for this exact amendment')
   binding={'status':'delivered_verified','chat_id':chat,'bot_id':bot,'plan_id':plan_id,'manifest':manifest,'manifest_sha256':digest(manifest),'expires_at':publication['expires_at'],'publication_key':new_key,'receipt_key':key,'amends_binding_archive':ROOT+':old_binding:'+str(receipt['message_id'])}
   db.update(bind_key,binding)
  publication.update(status='bound',bound_at=stamp());db.update(new_key,publication)
  old.update(status='superseded',superseded_by=plan_id,amendment_receipt=ROOT+':execution');db.update(old_key,old)
  # Dry approval validation in memory: verifies replies, membership, manifest and queue key.
  class DryDB:
   def get(self,key):return db.get(key)
   def once(self,key,value):
    if key!=COMMAND+'approved_report:'+plan_id or value['manifest']!=manifest:raise AssertionError('Dry approval differs')
  for mid in auth['message_ids'].values():
   message={'text':'Сделай всё','message_id':0,'chat':{'id':chat},'from':{'id':1,'is_bot':False},'reply_to_message':{'message_id':mid,'from':{'id':bot}}}
   dry=approve(DryDB(),message,COMMAND,chat,bot,membership={'status':'member','user':{'id':1}})
   if dry.get('status')!='approved_pending_execution':raise RuntimeError('Dry reply approval not ready')
  s.update(status='verified',verified_at=stamp(),plan_id=plan_id,action_count=len(manifest['actions']),message_ids=auth['message_ids'],manifest_sha256=digest(manifest),dry_reply_approval='passed_without_queue_write');save()
  print('Existing report photos verified and bound to amended actions; no new messages or WB calls')
 except Exception as error:
  s.update(status='attention',safe_error=str(error));save();raise
if __name__=='__main__':run()
