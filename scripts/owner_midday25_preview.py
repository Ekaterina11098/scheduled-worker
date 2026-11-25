"""Replay saved production evidence only; no WB/Telegram/model credentials or calls."""
import copy,json,base64,hashlib,requests
from urllib.parse import urlparse
from datetime import datetime,timezone
from china_advertising_state import AdvertisingIO
ROOT='china_agent:owner_midday_fix:2026-11-25:v2'
def main():
 io=AdvertisingIO();old=io.get(ROOT+':preview')
 if old:print('Existing preview retained');return
 original=requests.sessions.Session.request
 def guard(s,method,url,*a,**kw):
  u=urlparse(url);assert u.hostname==urlparse(io.url).hostname and u.path.startswith('/rest/v1/')and method.upper()in('GET','POST','PATCH'),'Saved-only replay';return original(s,method,url,*a,**kw)
 requests.sessions.Session.request=guard
 try:
  day='2026-11-25';saved=io.get('china_agent:advertising_midday_completed:'+day+':v1');review=copy.deepcopy(saved['review']);bundle=copy.deepcopy(io.get('china_agent:advertising_midday_artifacts:'+day+':ready-v2')['bundle'])
  source=copy.deepcopy(io.get('china_agent:advertising_source:'+day+':v2'));current=io.get('china_agent:advertising_midday_inclusive:'+day+':v1');inputs=io.get('china_agent:advertising_full_growth:'+day+':v1:inputs:midday')
  history={r['advertId']:r for b in source['batches'].values()for r in b['stats']}
  source['ids']=current['ids'];source['batches']=copy.deepcopy(current['batches'])
  for b in source['batches'].values():b['stats']=[history[c['id']]for c in b['campaigns']['adverts']if c['id']in history]
  source['full_growth_inputs']=inputs;source['economics']=inputs['economics'];source['config']=inputs['config'];source['period_to']='2026-11-24'
  from china_advertising_midday import current_report_context,render_midday,only_completed_day_actions
  from china_advertising_v2 import read_price_experience
  source['executions'],_=current_report_context(io,source,day)
  for name in('owner-revival25-verified','owner-aggressive25-verified'):
   alias='china_agent:ad_rule_execution:'+name+':v1';value=io.get(alias)
   if value:source['executions'].append(dict(cache_key=alias,payload=value))
  source['experience']=read_price_experience(io)
  minima={}
  for cid,q in inputs['minimums'].items():
   for n in q.get('bids',[]):
    vs=[b['value']for b in n['bids']if b['currency']=='CNY'];assert len(vs)==1;minima[str(cid)+':'+str(n['nm_id'])]=vs[0]
  # Restore all three original full-growth candidates before the common final pass.
  for proposal in review['sales_growth_review']['growth']:
   cp=next(c for c in review['campaigns']if c['id']==proposal['campaign_id']);r=next(r for r in cp['focus']if r['nm']==proposal['nm_id']);r.update(action=proposal['action'],decision=proposal.get('decision')or proposal['article']+': тест повысить '+str(proposal['action']['old_minor']/100)+' → '+str(proposal['action']['target_minor']/100)+' CNY.')
  from china_advertising_decision_contract import finalize
  from china_midday_completed_review import merge_completed
  new=finalize(io,review,source,minima);out=only_completed_day_actions(merge_completed(bundle,new,ROOT+':review'))
  # Assert exact ready actions, owner8%, protected row and empty archive presentation.
  from china_archived_report_window import midday_view
  visible=midday_view(out);actions=[r['action']for c in visible['campaigns']for r in c.get('attention',[])]
  assert not any(x['nm_id']in(1473243912,1473243825,1473244340)for x in actions),'Price24Nov still missing from completed window'
  assert out['target_drr_pct']==8 and 42022679 not in{c['id']for c in visible['campaigns']}
  assert next(c for c in visible['campaigns']if c['id']==42088552)['owner_unchanged']is True
  files=render_midday(out);proof=dict(status='verified',created_at=datetime.now(timezone.utc).isoformat(),review=new,bundle=out,visible_campaigns=[c['id']for c in visible['campaigns']],actions=actions,files=[dict(bytes_base64=base64.b64encode(f['bytes']).decode(),sha256=hashlib.sha256(f['bytes']).hexdigest(),page=f['page'],actions=f['actions'])for f in files],wb_writes=0,wb_reads=0,telegram_calls=0,model_calls=0)
  assert io.create(ROOT+':preview',proof);print(json.dumps(dict(status='verified',actions=len(actions),pages=len(files),wb_reads=0,wb_writes=0,telegram_calls=0)))
 finally:requests.sessions.Session.request=original
if __name__=='__main__':main()
