"""Replace exactly two approved existing OOO PNG messages; no new messages, WB or models."""
import os,json,base64,hashlib,datetime,time,requests
from china_codex_cloud import DB as BaseDB,stamp
ROOT='ooo_agent:report_replace:2026-11-17:v1'
class DB(BaseDB):
 def once(self,k,v):
  rows=self.api('POST','telegram_api_cache',body={'cache_key':k,'payload':v,'updated_at':stamp(),'expires_at':'2030-11-17T00:00:00Z'})
  if len(rows)!=1 or self.get(k)!=v:raise RuntimeError('Atomic edit claim failed')
def run():
 db=DB();a=db.get(ROOT+':authorization')or{}
 if a.get('status')!='approved'or a.get('operation')!='editMessageMedia_only'or a.get('chat_id')!=-1003987998401 or a.get('bot_id')!=9167526388 or{(x['kind'],x['message_id'])for x in a.get('images',[])}!={('advertising',43),('budgets',44)}:raise PermissionError('Exact replacement approval required')
 binding=db.get('ooo_agent:telegram_group:v1')or{}
 if binding.get('status')!='verified'or binding.get('chat_id')!=a['chat_id']:raise PermissionError('Current group binding mismatch')
 token=os.environ['OOO_TELEGRAM_BOT_TOKEN'];url='https://api.telegram.org/bot'+token
 me=requests.post(url+'/getMe',timeout=(10,30),allow_redirects=False)
 if me.status_code!=200 or me.json().get('result',{}).get('id')!=a['bot_id']:raise PermissionError('Bot identity mismatch')
 s=db.get(ROOT+':execution')
 if s and s.get('status')=='verified':print('Already edited; no repeat');return
 if not s:s={'status':'editing','started_at':stamp(),'edits':{},'wb_writes':0,'model_calls':0,'new_messages':0};db.once(ROOT+':execution',s)
 def save():
  if not db.update(ROOT+':execution',s):raise RuntimeError('Edit receipt persistence failed')
 try:
  for x in a['images']:
   prior=s['edits'].get(x['kind'])
   if prior:
    if prior.get('status')=='verified':continue
    raise RuntimeError('Prior edit outcome retained; no replay')
   original=db.get('ooo_agent:morning:2026-11-17:telegram:delivery:'+x['kind'])or{}
   if original.get('status')not in('sent','verified')or original.get('message_id')!=x['message_id']or original.get('chat_id')!=a['chat_id']:raise PermissionError('Original delivered receipt mismatch')
   raw=base64.b64decode(''.join(db.get(k)['data']for k in x['chunk_keys']))
   if len(raw)!=x['bytes']or hashlib.sha256(raw).hexdigest()!=x['sha256']:raise RuntimeError('Artifact hash/length mismatch')
   if db.get(ROOT+':authorization')!=a or datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(a['expires_at']):raise PermissionError('Approval changed or expired')
   receipt={'status':'submitting','message_id':x['message_id'],'chat_id':a['chat_id'],'sha256':x['sha256'],'submitted_at':stamp()}
   s['edits'][x['kind']]=receipt;save()
   try:r=requests.post(url+'/editMessageMedia',data={'chat_id':str(a['chat_id']),'message_id':str(x['message_id']),'media':json.dumps({'type':'photo','media':'attach://photo'})},files={'photo':(x['kind']+'.png',raw,'image/png')},timeout=(10,60),allow_redirects=False)
   except requests.RequestException:
    receipt['status']='uncertain';save();raise RuntimeError('Edit transport uncertain; no repeat')from None
   try:body=r.json()
   except ValueError:body={}
   result=body.get('result',{})
   if r.status_code!=200 or not body.get('ok')or result.get('message_id')!=x['message_id']or result.get('chat',{}).get('id')!=a['chat_id']:
    receipt.update(status='uncertain'if r.status_code==200 else'rejected',http_status=r.status_code,description=body.get('description'));save();raise RuntimeError('Telegram edit not confirmed')
   receipt.update(status='verified',verified_at=stamp(),file_id=result.get('photo',[{}])[-1].get('file_id'));save()
  s.update(status='verified',verified_at=stamp());save()
  publication='ooo_agent:sol_dialog:v1:publication:morning-2026-11-17';p=db.get(publication)
  if p:
   p['display_replacement']={'status':'verified','receipt_key':ROOT+':execution','artifact_sha256':[x['sha256']for x in a['images']],'message_ids':[43,44],'manifest_unchanged':True};db.update(publication,p)
  print('Existing two PNG messages replaced and verified; no new messages or WB calls')
 except Exception as e:s.update(status='attention',safe_error=str(e));save();raise
if __name__=='__main__':run()
