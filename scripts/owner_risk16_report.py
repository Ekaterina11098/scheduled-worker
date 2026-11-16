"""Owner-requested two-campaign review and same-message proposal update; never executes WB."""
import base64,copy,hashlib,json
from datetime import datetime,timezone
from urllib.parse import urlparse
ROOT='china_agent:owner_two_campaign_cost_review:2026-11-16:v2';DAY='2026-11-16';IDS={41325637,41332083};EXPECTED={(41332083,1473245505),(41332083,1473246032)};HELD_NM=1473243903

def reviewed(bundle,source,minima):
 from china_advertising_economic_review import apply
 result=copy.deepcopy(bundle);part=copy.deepcopy(bundle)
 part['campaigns']=[c for c in part['campaigns']if c['id']in IDS]
 growth={c['id']:[r for r in c['focus']if(r.get('action')or{}).get('kind')=='ad_add_sku'and r['nm']!=HELD_NM]for c in part['campaigns']}
 for c in part['campaigns']:c['focus']=[r for r in c['focus']if(r.get('action')or{}).get('kind')!='ad_add_sku']
 part=apply(part,source,minima)
 actions={(c['id'],r['nm']):r for c in part['campaigns']for r in c['focus']if r.get('action')}
 assert set(actions)==EXPECTED,('Unexpected scope of cost recommendations',list(actions))
 for c in part['campaigns']:
  c['focus']+=growth[c['id']];c['attention']=[r for r in c['focus']if r.get('action')]
  result['campaigns']=[c if old['id']==c['id']else old for old in result['campaigns']]
 for (cid,nm),r in actions.items():
  section=result['recommendation_directions']['exclude']
  section['rows']=[x for x in section['rows']if not(x.get('campaign_id')==cid and x.get('nm_id')==nm)]
  section['rows'].append(dict(article=r['article'],campaign_id=cid,nm_id=nm,decision=r['decision'],action=r['action'],period=r['period'],evaluation_days=(r.get('comparison')or{}).get('to_days',[]),economics=r['economics'],ready=True))
  section.update(count=len(section['rows']),ready_count=sum(x.get('ready')is True for x in section['rows']),note=str(len(section['rows']))+' готовых предложений; только после согласования.')
 for section in result['recommendation_directions'].values():
  section['rows']=[r for r in section['rows']if r.get('nm_id')!=HELD_NM]
  section.update(count=len(section['rows']),ready_count=sum(r.get('ready')is True for r in section['rows']))
 result['owner_cost_review']=dict(source_day=DAY,campaigns=sorted(IDS),ready_exclusions=[dict(campaign_id=c,nm_id=n)for c,n in sorted(EXPECTED)],held_nm_excluded=HELD_NM,wb_writes=0,model_calls=0)
 return result

def main():
 import requests
 from china_advertising_state import AdvertisingIO
 io=AdvertisingIO()
 if(io.get(ROOT)or{}).get('status')=='delivered':return
 assert not io.get(ROOT),'Existing review journal needs inspection, never blind retry'
 original=requests.sessions.Session.request
 def guarded(session,method,url,**kw):
  u=urlparse(url);m=method.upper();host=u.hostname or''
  if host=='advert-api.wildberries.ru':assert(m=='GET'and u.path=='/api/advert/v2/adverts')or(m=='POST'and u.path=='/api/advert/v1/bids/min')
  elif host=='api.telegram.org':assert m=='POST'and u.path.rsplit('/',1)[-1]=='editMessageMedia'
  elif not url.startswith(io.url+'/rest/v1/'):raise ValueError('Unrelated transport forbidden')
  return original(session,method,url,**kw)
 requests.sessions.Session.request=guarded
 from china_advertising_v2 import http
 from china_daily_ad_actions import plan,bind,BIND
 from china_report_buttons import prepare as buttons,claim,ROOT as BUTTONS
 from china_loss_control import PLAN,CHAT,BOT
 key='china_agent:advertising_artifacts:'+DAY+':v2';dk='china_agent:advertising_delivery:'+DAY+':v1'
 old=io.get(key);delivery=io.get(dk);assert delivery['status']=='delivered'
 f_old=next(f for f in old['files']if f['family']=='drr');parent=f_old['plan_id']
 def unclaimed():assert not(io.get('china_agent:daily_action_claim:v1:'+parent)or{}).get('domains'),'Report already confirmed; do not replace'
 unclaimed()
 source=io.get('china_agent:advertising_source:'+DAY+':v2');assert source['day_quality']['usable']and source['full_growth_review']['status']=='complete'
 prior=io.get(ROOT.replace(':v2',':v1'))or{}
 reuse=prior.get('status')=='delivered'and(datetime.now(timezone.utc)-datetime.fromisoformat(prior['completed_at'])).total_seconds()<600
 live=prior['live']if reuse else http(io,'/api/advert/v2/adverts?ids=41325637,41332083')['adverts'];assert {c['id']for c in live}==IDS
 saved={c['id']:c for b in source['batches'].values()for c in b['campaigns']['adverts']}
 for c in live:
  before=saved[c['id']]
  assert c['status']==before['status']==9
  core=lambda state:sorted((n['nm_id'],n['bids_kopecks']['search'],n['subject']['id'])for n in state['nm_settings'])
  assert core(c)==core(before),'Campaign changed after source; recollect before proposal'
  assert c['settings']==before['settings']
 quote=prior['minimum_quote']if reuse else http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=41332083,nm_ids=[1473245505,1473246032],payment_type='cpc',placement_types=['search']))
 minima={}
 for row in quote['bids']:
  vals=[q['value']for q in row['bids']if q['type']=='search'and q['currency']=='CNY'];assert vals==[28]
  minima['41332083:'+str(row['nm_id'])]=28
 assert len(minima)==2
 umbrella_quote=prior['umbrella_quote']if reuse else http(io,'/api/advert/v1/bids/min','POST',dict(advert_id=41325637,nm_ids=[1556488181],payment_type='cpc',placement_types=['search']))
 assert [v['value']for r in umbrella_quote['bids']for v in r['bids']if r['nm_id']==1556488181 and v['type']=='search'and v['currency']=='CNY']==[27]
 bundle=reviewed(old['bundle'],source,minima)
 from china_advertising_v2_png import render
 pages=render(bundle);page=next(f for f in pages if f['family']=='drr');assert sum(f['family']=='drr'for f in pages)==1
 oldplan=io.get(PLAN+parent);newids={a['id']for a in page['actions']};oldids={a['id']for a in oldplan['items']}
 heldids={a['id']for a in oldplan['items']if a.get('nm_id')==HELD_NM}
 assert newids==(oldids-heldids)|{'41332083:1473245505','41332083:1473246032'}
 new=plan(io,DAY,page,0,slot='cost-review-two16-holds')
 markup=buttons(io,new,'drr');assert markup and any('Исключить' in b['text']for row in markup['inline_keyboard']for b in row)
 unclaimed();claim(io,parent,['drr'],'replace:'+ROOT)
 journal=dict(status='prepared',created_at=datetime.now(timezone.utc).isoformat(),wb_writes=0,model_calls=0,live=live,minimum_quote=quote,umbrella_quote=umbrella_quote,new_plan_id=new['plan_id'])
 before=copy.deepcopy(old)
 for f in before['files']:f.pop('b64',None)
 assert io.create(ROOT,journal);assert io.create(ROOT+':before',before);assert io.create(ROOT+':before_delivery',delivery);assert io.create(ROOT+':review',bundle)
 oldplan.update(invalidated_at=datetime.now(timezone.utc).isoformat(),invalidation_reason='Owner requested completed two-campaign cost review in the same report');io.put(PLAN+parent,oldplan)
 part=next(p for p in delivery['parts']if p['kind']==f_old['kind']);mid=part['message_id'];assert mid==1053
 journal.update(status='editing',message_id=mid);io.put(ROOT,journal)
 caption='Китай · реклама и рекомендации по РК · '+DAY+'. Добавлен разбор двух РК. Новых действий: '+str(len(new['items']))+'. Выберите нужное → «Посмотреть выбранное» → «Подтвердить».'
 try:
  r=requests.post('https://api.telegram.org/bot'+io.bot+'/editMessageMedia',data=dict(chat_id=CHAT,message_id=mid,media=json.dumps(dict(type='photo',media='attach://photo',caption=caption),ensure_ascii=False),reply_markup=json.dumps(markup,ensure_ascii=False)),files={'photo':('report.png',page['bytes'],'image/png')},timeout=60)
  response=r.json();assert r.ok and response.get('ok');receipt=response['result'];assert receipt['message_id']==mid and receipt['chat']['id']==CHAT
 except Exception:
  journal['status']='uncertain';io.put(ROOT,journal);raise
 binding=dict(plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],chat_id=CHAT,family='drr');io.put(BIND+str(mid),binding)
 token=markup['inline_keyboard'][0][0]['callback_data'].split(':')[1]
 io.put(BUTTONS+'message:'+str(mid),dict(status='sent',token=token,plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],family='drr',chat_id=CHAT,bot_id=BOT,message_id=mid,receipt=receipt))
 bind(io,dict(plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],family='drr'),receipt)
 file=dict(kind=page['kind'],family='drr',page=page['page'],total=page['total'],plan_id=new['plan_id'],plan_sha256=new['plan_sha256'],action_count=len(new['items']),b64=base64.b64encode(page['bytes']).decode())
 old['files']=[file if f['family']=='drr'else f for f in old['files']];old.update(bundle=bundle,corrected_by=ROOT);io.put(key,old)
 part.update(sha256=hashlib.sha256(page['bytes']).hexdigest(),receipt=receipt,corrected_by=ROOT,corrected_at=datetime.now(timezone.utc).isoformat());io.put(dk,delivery)
 assert io.get(PLAN+new['plan_id'])['report_message_ids']==[mid]
 assert io.get(BIND+str(mid))==binding
 journal.update(status='delivered',receipt=receipt,completed_at=datetime.now(timezone.utc).isoformat(),new_action_count=len(newids-oldids),removed_held_actions=sorted(heldids),total_action_count=len(new['items']));io.put(ROOT,journal)
 print(json.dumps(dict(status='delivered',message_id=mid,exclusions=sorted(n for c,n in EXPECTED),new_actions=2,wb_writes=0,model_calls=0)))
if __name__=='__main__':main()
