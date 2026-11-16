"""Caption-only PNG correction of existing delivered midday report. No WB credential/API."""
import os,json,base64,hashlib,copy,requests
from china_cloud_cost_control import Cache,stamp
from china_advertising_midday import render_midday
from china_loss_control import digest
DAY='2026-11-16';MID=1060;CHAT=-1004342917488;BOT=8780468043
KEY='china_agent:owner_midday1060_caption:2026-11-16:v1'
def main():
 c=Cache();ak='china_agent:advertising_midday_artifacts:'+DAY+':ready-v2';dk='china_agent:advertising_midday_delivery:'+DAY+':ready-v2'
 art=c.get(ak);delivery=c.get(dk);binding=c.get('china_agent:daily_ad_message:v2:'+str(MID))
 assert art['status']=='frozen'and delivery['status']=='delivered'and len(art['files'])==len(delivery['parts'])==1
 part=delivery['parts'][0];receipt=part['receipt'];assert part['status']=='sent'and part['message_id']==MID and receipt['chat']['id']==CHAT and receipt['from']['id']==BOT
 assert binding['plan_id']==art['files'][0]['plan_id']and binding['plan_sha256']==art['files'][0]['plan_sha256']
 old=base64.b64decode(art['files'][0]['b64']);assert hashlib.sha256(old).hexdigest()==part['sha256']
 p=c.get('china_agent:loss_plan:v1:'+binding['plan_id'])
 assert p and p['plan_sha256']==digest(p['items'])==binding['plan_sha256']
 b=copy.deepcopy(art['bundle']);removed=[]
 for cp in b['campaigns']:
  ready={r['article']for r in cp['attention']if r['action']['kind']=='ad_add_sku'}
  notes=cp.get('addition_review_notes',[])
  cp['addition_review_notes']=[n for n in notes if not any(n.startswith(a+':')for a in ready)]
  removed += [n for n in notes if n not in cp['addition_review_notes']]
 assert len(removed)==1 and removed[0].startswith('534-NoelBag-emerald:')
 pages=render_midday(b);assert len(pages)==1 and pages[0]['actions']==p['items']
 blob=pages[0]['bytes'];sha=hashlib.sha256(blob).hexdigest()
 rec=dict(status='prepared',message_id=MID,chat_id=CHAT,plan_id=p['plan_id'],plan_sha256=p['plan_sha256'],before_sha256=part['sha256'],after_sha256=sha,removed=removed,wb_writes=0,created_at=stamp())
 if not c.create(KEY,rec):raise RuntimeError('Existing edit journal; never repeat')
 assert c.create(KEY+':original',dict(artifact=art,delivery=delivery))
 rec['status']='submitting';c.put(KEY,rec)
 try:
  r=requests.post('https://api.telegram.org/bot'+os.environ['CHINA_TELEGRAM_BOT_TOKEN']+'/editMessageMedia',data=dict(chat_id=str(CHAT),message_id=str(MID),media=json.dumps(dict(type='photo',media='attach://photo',caption=receipt['caption']),ensure_ascii=False),reply_markup=json.dumps(receipt['reply_markup'],ensure_ascii=False)),files={'photo':('midday.png',blob,'image/png')},timeout=60)
  j=r.json();assert r.ok and j.get('ok');actual=j['result']
  assert actual['message_id']==MID and actual['chat']['id']==CHAT and actual['from']['id']==BOT
 except Exception:
  rec['status']='uncertain';c.put(KEY,rec);raise
 rec.update(status='edited',receipt=actual,edited_at=stamp());c.put(KEY,rec)
 art['bundle']=b;art['files'][0]['b64']=base64.b64encode(blob).decode();art['caption_correction_key']=KEY;c.put(ak,art)
 part['sha256']=sha;part['receipt']=actual;part['last_edit_receipt_key']=KEY;part['last_edited_at']=rec['edited_at'];c.put(dk,delivery)
 c.put(KEY+':verified',dict(status='verified',message_id=MID,actions_unchanged=True,plan_sha256=p['plan_sha256'],delivery_status='delivered',edited_at=rec['edited_at'],wb_writes=0))
 print(json.dumps(dict(status='edited_verified',message_id=MID,actions=len(p['items']),new_messages=0,wb_writes=0)))
if __name__=='__main__':main()
