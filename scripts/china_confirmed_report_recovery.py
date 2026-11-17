"""Bounded retries only for read-only preflight failures; never replay uncertain writes."""
import copy
TRANSIENT={'ConnectTimeout','ReadTimeout','Timeout','ConnectionError','State HTTP 429','State HTTP 500','State HTTP 502','State HTTP 503','State HTTP 504'}
def retryable(state):
 return state.get('status')=='blocked'and state.get('reason')in TRANSIENT and state.get('preflight_rechecks',0)<2 and not state.get('request')and not state.get('bid_phase')and not state.get('wb_writes')and all(s.get('read_only')is True for s in state.get('steps',[]))
def recheck(state):
 if not retryable(state):raise ValueError('Only unsubmitted transient read preflight may be retried')
 history=copy.deepcopy(state.get('preflight_failures',[]));old={k:copy.deepcopy(v)for k,v in state.items()if k!='preflight_failures'};history.append(old)
 value=dict(id=state['id'],status='preflight',preflight_rechecks=state.get('preflight_rechecks',0)+1,preflight_failures=history)
 state.clear();state.update(value)
def register_campaigns(io,p,e):
 from china_execution_notice import proven
 items={i['id']:i for i in p['items']};registry=io.get('china_agent:verified_campaign_state:v1')or{};changed=False
 for cid in {i['campaign_id']for i in p['items']}:
  rows=[s for s in e['items']if items[s['id']]['campaign_id']==cid]
  if not rows or not all(proven(items[s['id']],s)for s in rows):continue
  latest=max(rows,key=lambda s:s.get('verified_at',''));after=latest.get('after')
  if not after:continue
  at=latest.get('verified_at')or e.get('completed_at','');old=io.get(registry.get(str(cid),''))or{}
  if old.get('verified_at','')>at:continue
  key='china_agent:daily_ad_execution:v2:'+p['plan_id']+':verified_campaign:'+str(cid)
  value=dict(status='verified',after=after,verified_at=at,parent_plan_id=p['plan_id'])
  saved=io.get(key)
  if saved is None:
   if not io.create(key,value):raise ValueError('Verified campaign receipt publication conflict')
  elif saved!=value:continue
  registry[str(cid)]=key;changed=True
 if changed:io.put('china_agent:verified_campaign_state:v1',registry)
