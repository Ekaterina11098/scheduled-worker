"""Owner-authorized same-message report revisions; no WB mutations or model calls."""
import copy,json,base64,hashlib
from datetime import datetime,timezone
ROOT='china_agent:owner_two_campaign_cost_review:2026-11-16:v3';DAY='2026-11-16';NM=1473243903;CID=41332083
SLOT='cost-review-two16-current';EXPECTED_ADDED={'41332083:add:1473243903'};EXPECTED_REMOVED=set()
OWNER_REQUEST='нет у меня таких распоряжений не возвращать отдельные арт'
PREFLIGHT=None;ALLOW_UMBRELLA_READS=False;READ_CAMPAIGN_IDS={41325637}

def restore(current,prior):
 out=copy.deepcopy(current)
 candidate=next(r for c in prior['campaigns']if c['id']==CID for r in c['focus']if r['nm']==NM and(r.get('action')or{}).get('kind')=='ad_add_sku')
 e=candidate['action']['growth_evidence']
 assert e['expected_margin_before_ads_cny']>0 and e['stock_free']>0 and e['published_stock']>0 and not e['buyout_fallback']
 assert 0<=(datetime.now(timezone.utc)-datetime.fromisoformat(e['observed_at'])).total_seconds()<24*3600
 c=next(c for c in out['campaigns']if c['id']==CID)
 assert not any(r['nm']==NM and r.get('action')for r in c['focus'])
 c['focus'].append(copy.deepcopy(candidate));c['attention']=[r for r in c['focus']if r.get('action')]
 row=next(r for r in prior['recommendation_directions']['add']['rows']if r.get('nm_id')==NM and r.get('campaign_id')==CID and r.get('ready'))
 section=out['recommendation_directions']['add'];section['rows'].append(copy.deepcopy(row));section.update(count=len(section['rows']),ready_count=sum(r.get('ready')is True for r in section['rows']))
 out.setdefault('owner_cost_review',{}).pop('held_nm_excluded',None)
 out['owner_cost_review']['current_owner_correction']='No standing no-return restriction on SKU534; exact proposal restored, no execution authorized.'
 return out

def main():
 import requests
 from urllib.parse import urlparse
 from china_advertising_state import AdvertisingIO
 from china_daily_ad_actions import plan,bind,BIND
 from china_report_buttons import prepare as buttons,claim,ROOT as BUTTONS
 from china_loss_control import PLAN,CHAT,BOT
 io=AdvertisingIO()
 if(io.get(ROOT)or{}).get('status')=='delivered':return
 assert not io.get(ROOT),'Inspect existing journal; no blind retry'
 original=requests.sessions.Session.request
 def guard(session,method,url,**kw):
  u=urlparse(url)
  from urllib.parse import parse_qs
  query_ids=parse_qs(u.query).get('ids',[''])[0].split(',')
  ids_ok=bool(query_ids)and all(x.isdigit()and int(x)in READ_CAMPAIGN_IDS for x in query_ids)
  read_ok=ALLOW_UMBRELLA_READS and u.hostname=='advert-api.wildberries.ru'and(method.upper()=='GET'and u.path=='/api/advert/v2/adverts'and ids_ok or method.upper()=='POST'and u.path=='/api/advert/v1/bids/min'and(kw.get('json')or{}).get('advert_id')in READ_CAMPAIGN_IDS)
  assert read_ok or url.startswith(io.url+'/rest/v1/')or u.hostname=='api.telegram.org'and method.upper()=='POST'and u.path.rsplit('/',1)[-1]=='editMessageMedia','No WB mutations, model or unrelated calls'
  return original(session,method,url,**kw)
 requests.sessions.Session.request=guard
 key='china_agent:advertising_artifacts:'+DAY+':v2';dk='china_agent:advertising_delivery:'+DAY+':v1';old=io.get(key);delivery=io.get(dk)
 f_old=next(f for f in old['files']if f['family']=='drr');parent=f_old['plan_id']
 assert not(io.get('china_agent:daily_action_claim:v1:'+parent)or{}).get('domains'),'Current report confirmed; cannot replace'
 prior=io.get('china_agent:owner_two_campaign_cost_review:2026-11-16:v1:review')
 if PREFLIGHT:checks=PREFLIGHT(io,old['bundle'])
 else:checks={}
 bundle=restore(old['bundle'],prior)
 from china_advertising_v2_png import render
 page=next(f for f in render(bundle)if f['family']=='drr');oldplan=io.get(PLAN+parent)
 oldids={i['id']for i in oldplan['items']};newids={i['id']for i in page['actions']};assert newids==(oldids-EXPECTED_REMOVED)|EXPECTED_ADDED
 new=plan(io,DAY,page,0,slot=SLOT);markup=buttons(io,new,'drr');assert markup
 claim(io,parent,['drr'],'replace:'+ROOT)
 journal=dict(status='prepared',created_at=datetime.now(timezone.utc).isoformat(),owner_correction=OWNER_REQUEST,wb_writes=0,model_calls=0,new_plan_id=new['plan_id'],checks=checks);assert io.create(ROOT,journal)
 assert io.create(ROOT+':review',bundle)
 oldplan.update(invalidated_at=datetime.now(timezone.utc).isoformat(),invalidation_reason='Current owner requested updated campaign recommendations');io.put(PLAN+parent,oldplan)
 part=next(p for p in delivery['parts']if p['kind']==f_old['kind']);mid=part['message_id'];assert mid==1053
 journal.update(status='editing',message_id=mid);io.put(ROOT,journal)
 caption='Китай · реклама и рекомендации по РК · '+DAY+'. Общий отчёт. Новых действий: '+str(len(new['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
 try:
  r=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=CHAT,message_id=mid,media=json.dumps(dict(type='photo',media='attach://photo',caption=caption),ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('report.png',page['bytes'],'image/png')},timeout=60)
  j=r.json();assert r.ok and j.get('ok');receipt=j['result'];assert receipt['message_id']==mid and receipt['chat']['id']==CHAT
 except Exception:journal['status']='uncertain';io.put(ROOT,journal);raise
 binding=dict(plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],chat_id=CHAT,family='drr');io.put(BIND+str(mid),binding)
 token=markup['inline_keyboard'][0][0]['callback_data'].split(':')[1]
 io.put(BUTTONS+'message:'+str(mid),dict(status='sent',token=token,plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],family='drr',chat_id=CHAT,bot_id=BOT,message_id=mid,receipt=receipt));bind(io,dict(plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],family='drr'),receipt)
 f=dict(kind=page['kind'],family='drr',page=page['page'],total=page['total'],plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],action_count=len(new['items']),b64=base64.b64encode(page['bytes']).decode())
 old['files']=[f if r['family']=='drr'else r for r in old['files']];old.update(bundle=bundle,corrected_by=ROOT);io.put(key,old)
 part.update(sha256=hashlib.sha256(page['bytes']).hexdigest(),receipt=receipt,corrected_by=ROOT,corrected_at=datetime.now(timezone.utc).isoformat());io.put(dk,delivery)
 assert io.get(BIND+str(mid))==binding
 journal.update(status='delivered',message_id=mid,receipt=receipt,total_action_count=len(new['items']),completed_at=datetime.now(timezone.utc).isoformat());io.put(ROOT,journal)
 print(json.dumps(dict(status='delivered',message_id=mid,total_action_count=len(new['items']),added_proposals=len(newids-oldids),removed_proposals=len(oldids-newids),wb_writes=0,model_calls=0)))
if __name__=='__main__':main()
