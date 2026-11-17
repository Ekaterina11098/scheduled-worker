"""Cached unified-decision replay and readback of seven already submitted actions. No WB writes."""
import os,json,copy
from urllib.parse import urlparse
import requests
from china_cloud_cost_control import Cache,WB,validate_identity,stamp
from china_advertising_decision_contract import finalize,REVISION
from china_advertising_v2 import sums,daily_metrics
ROOT='china_agent:unified_decisions:2026-11-17:v1'
PLAN='daily-2026-11-17-midday-ready-v2-drr-0-buttons-fe81474d3b733b0445d66943-5122667182'
def main():
 c=Cache();w=WB();validate_identity(c,w)
 original=requests.sessions.Session.request
 def guard(session,method,url,*a,**kw):
  u=urlparse(url);m=method.upper()
  if u.hostname==urlparse(os.environ['SUPABASE_URL']).hostname:ok=u.path.startswith('/rest/v1/')and m in('GET','POST','PATCH')
  elif u.hostname=='advert-api.wildberries.ru':ok=m=='GET'and u.path=='/api/advert/v2/adverts'
  elif u.hostname=='api.telegram.org':ok=m=='POST'and u.path.endswith('/editMessageText')and (kw.get('json')or{}).get('chat_id')==-1004342917488 and (kw.get('json')or{}).get('message_id')==1087
  else:ok=False
  assert ok,'Verification forbids marketplace mutation and new Telegram messages'
  return original(session,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 try:
  ekey='china_agent:daily_ad_execution:v2:'+PLAN;e=c.get(ekey);p=c.get('china_agent:loss_plan:v1:'+PLAN);a=c.get('china_agent:loss_plan_approval:v1:344')
  assert len(e['items'])==7 and len(p['items'])==7 and a['plan_id']==PLAN
  states=w.campaigns([41055480,41270309,41298169]);byid={i['id']:i for i in p['items']}
  def projection(cp):return {k:cp[k]for k in('id','status','currency','bid_type','settings','nm_settings')}
  c.put(ROOT+':current_campaigns',dict(observed_at=stamp(),campaigns=states,wb_writes=0))
  def verify_seven():
   for cid in states:
    rows=[x for x in e['items']if str(byid[x['id']]['campaign_id'])==cid];expected=copy.deepcopy(rows[0]['before'])
    for row in rows:
     i=byid[row['id']]
     if i['kind']=='ad_exclude_sku':expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']!=i['nm_id']]
     else:next(n for n in expected['nm_settings']if n['nm_id']==i['nm_id'])['bids_kopecks'][i['placement']]=i['target_minor']
    expected['nm_settings'].sort(key=lambda n:n['nm_id']);actual=copy.deepcopy(states[cid]);actual['nm_settings'].sort(key=lambda n:n['nm_id'])
    assert projection(actual)==projection(expected),'Current WB differs from approved batch '+cid
   for row in e['items']:
    if row['status']=='verified':continue
    assert row['status']in('accepted','uncertain')
    cid=byid[row['id']]['campaign_id'];before=copy.deepcopy(row['before']);expected=copy.deepcopy(before)
    expected['nm_settings']=[n for n in expected['nm_settings']if n['nm_id']!=byid[row['id']]['nm_id']]
    expected['nm_settings'].sort(key=lambda n:n['nm_id']);actual=copy.deepcopy(states[str(cid)]);actual['nm_settings'].sort(key=lambda n:n['nm_id'])
    assert projection(expected)==projection(actual),'Individual final readback differs; do not rewrite'
    row.update(status='verified',after=states[str(cid)],verified_at=stamp(),readback_recovery='read_only_no_repeated_write')
   e.update(status='done',completed_at=stamp(),readback_recovery_at=stamp());c.put(ekey,e)
   from china_confirmed_report_recovery import register_campaigns
   register_campaigns(c,p,e)
   from china_advertising_state import AdvertisingIO
   from china_execution_notice import deliver_result
   notice=deliver_result(AdvertisingIO(),a,p,e)
   assert notice and notice['status']=='sent'and notice['phase']=='verified'and notice['message_id']==1087
   c.put(ROOT+':execution_readback',dict(status='verified',items=7,campaigns=states,source_execution_key=ekey,result_message_id=1087,wb_writes=0,verified_at=stamp()))
  try:
   verify_seven();seven_ok=True
  except AssertionError as error:
   seven_ok=False;c.put(ROOT+':execution_readback',dict(status='needs_review',reason=str(error),wb_writes=0,checked_at=stamp()))
  # Replay actual dated frozen inputs; no collection/model/Telegram traffic.
  s=c.get('china_agent:advertising_source:2026-11-17:v2')
  frozen=c.get('china_agent:advertising_midday_completed:2026-11-17:v1');compact=c.get(frozen['source_ref'])
  s['economics']=(c.get('china_agent:advertising_full_growth:2026-11-17:v1:inputs:midday')or{}).get('economics',compact['economics']);s['completed_cost_ledger']=c.get('china_agent:completed_campaign_cost:v2')or{}
  s['verified_composition_changes']=[dict(nm=x['nm'],cid=x.get('campaign_id'),kind=x['kind'],at=x['at'])for x in compact['changes']]
  observed={cp['id']:cp for batch in s['batches'].values()for cp in batch['campaigns']['adverts']}
  observed.update({i['before']['id']:i['before']for i in reversed(e['items'])})
  campaigns=[]
  for cp in compact['current_campaigns']:
   cp=copy.deepcopy(cp);cp['restrictions']=copy.deepcopy(observed.get(cp['id'],{}).get('restrictions',{}))
   for n in cp['nm_settings']:n['subject']={'id':n.pop('subject_id',50)}
   campaigns.append(cp)
  raw={}
  cols=compact['product_daily_columns'];fields=dict(spend='sum',amount='sum_price',orders='orders',clicks='clicks',views='views',baskets='atbs')
  for pr in compact['products'].values():
   cp=raw.setdefault(pr['campaign_id'],{})
   for day,values in pr['daily'].items():
    n={fields[k]:v for k,v in zip(cols,values)};n['nmId']=pr['nm_id'];cp.setdefault(day,[]).append(n)
  stats=[]
  for cid,ds in raw.items():
   stats.append(dict(advertId=cid,days=[dict(date=d,apps=[dict(nms=ns)],**{f:sum(n.get(f,0)for n in ns)for f in fields.values()})for d,ns in sorted(ds.items())]))
  s['batches']={'0':dict(campaigns={'adverts':campaigns},stats=stats,budgets={'adverts':[]})}
  if s.get('full_growth_inputs'):s['full_growth_inputs']['campaigns']=campaigns
  b=frozen['review'];mins={str(cp['id'])+':'+str(r['nm']):r['minimum_bid_minor']for cp in b['campaigns']for r in cp.get('focus',[])if type(r.get('minimum_bid_minor'))is int}
  outputs=[]
  for label in('morning','midday','analyst'):
   out=finalize(c,copy.deepcopy(b),copy.deepcopy(s),dict(mins))
   outputs.append(out['decision_contract'])
  assert outputs[0]==outputs[1]==outputs[2],'Report surfaces disagree'
  item=next(r for r in outputs[0]['rows']if r['campaign_id']==41270309 and r['nm_id']==1473246045)
  assert item['decision_window']['days']==['2026-11-16']and abs(item['decision_window']['metrics']['spend']-15.92)<.001
  c.put(ROOT+':regression',dict(status='verified',revision=REVISION,surfaces=['morning','midday','analyst'],identical=True,case631=item,rows=len(outputs[0]['rows']),decision_contract=outputs[0],wb_writes=0,model_calls=0,new_telegram_messages=0,checked_at=stamp()))
  print(json.dumps(dict(status='verified',items7verified=seven_ok,three_surfaces_identical=True,case631_days=item['decision_window']['days'],wb_writes=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
