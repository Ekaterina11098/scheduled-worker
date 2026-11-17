"""Reconcile only the approved final four-SKU paused composition; no funding/start."""
import copy,json,time
from datetime import datetime,timezone
ROOT='china_agent:owner_finish340:2026-11-17:v1'
CID=41779660;REMOVE=2129309886;BID=2129309885
def main():
 from china_loss_execute import IO
 from china_loss_control import PLAN,APPROVAL
 from china_daily_ad_actions import EXEC
 from china_selected_campaign_test import publish_preparation
 from china_execution_notice import deliver_result,proven
 import requests
 io=IO();a=io.get(APPROVAL+'340');p=io.get(PLAN+a['plan_id']);io.validate_owner(a)
 e=io.get(EXEC+p['plan_id']);assert len(p['items'])==35 and len(e['items'])==35
 items={x['id']:x for x in p['items']};uncertain=[s for s in e['items']if s['status']!='verified']
 assert len(uncertain)==1 and items[uncertain[0]['id']]['nm_id']==REMOVE
 ref='china_agent:selected_campaign_preparation:v1:41779660:20261117-r2';prep=io.get(ref);target=prep['target_bids'];keep=set(map(int,target))
 record=io.get(ROOT)
 assert not record,'Never blindly replay this reconciliation'
 record=dict(status='preflight',job_id=340,original_uncertain=copy.deepcopy(uncertain[0]),writes=[],funding=0,starts=0)
 assert io.create(ROOT,record)
 def save():io.put(ROOT,copy.deepcopy(record))
 def req(path,method='GET',body=None):
  response=requests.request(method,'https://advert-api.wildberries.ru'+path,headers={'Authorization':io.token},json=body,timeout=50);response.raise_for_status();return response.json()if response.content else{}
 def read():
  rows=req('/api/advert/v2/adverts?ids='+str(CID))['adverts'];assert len(rows)==1;v=rows[0]
  assert v['id']==CID and v['status']==11 and v['currency']=='CNY'
  bids={str(n['nm_id']):n['bids_kopecks']for n in v['nm_settings']}
  assert keep<=set(map(int,bids))<=keep|{REMOVE}
  for nm,b in bids.items():assert b==target.get(nm,{'search':0,'recommendations':28})or int(nm)==BID and b=={'search':0,'recommendations':50}
  return v
 first=read();time.sleep(5);before=read();assert first==before;record['before']=before;save()
 def mutation(label,path,body):
  from china_daily_report_validity import require
  require(io,p)
  row=dict(label=label,status='submitting',body=body);record['writes'].append(row);save()
  row['response']=req(path,'PATCH',body);row['status']='accepted';save()
 if any(n['nm_id']==REMOVE for n in before['nm_settings']):
  mutation('exclude_present_approved_sku','/adv/v0/auction/nms',dict(nms=[dict(advert_id=CID,nms=dict(add=[],delete=[REMOVE]))]))
  for _ in range(25):
   got=read()
   if {n['nm_id']for n in got['nm_settings']}==keep:break
   time.sleep(3)
  else:raise ValueError('Exclusion readback pending; no automatic repeat')
  record['writes'][-1]['status']='verified';save()
 else:got=before
 state=uncertain[0];state['original_uncertain_attempt']=copy.deepcopy(record['original_uncertain']);state.update(before=before,after=got,status='verified',recovery_key=ROOT,verified_at=datetime.now(timezone.utc).isoformat())
 assert proven(items[state['id']],state)or REMOVE not in{n['nm_id']for n in before['nm_settings']}
 member=next(n for n in got['nm_settings']if n['nm_id']==BID)
 if member['bids_kopecks']['recommendations']!=28:
  quote=req('/api/advert/v1/bids/min','POST',dict(advert_id=CID,nm_ids=[BID],payment_type='cpc',placement_types=['recommendation']))
  values=[b['value']for n in quote['bids']for b in n['bids']if b['currency']=='CNY'and b['type']=='recommendation'];assert len(values)==1 and values[0]<=28
  mutation('restore_exact_approved_bid_after_composition','/api/advert/v1/bids',dict(bids=[dict(advert_id=CID,nm_bids=[dict(nm_id=BID,placement='recommendations',bid_kopecks=28)])]))
  for _ in range(25):
   got=read()
   if all(n['bids_kopecks']==target[str(n['nm_id'])]for n in got['nm_settings']):break
   time.sleep(3)
  else:raise ValueError('Bid readback pending; no automatic repeat')
  record['writes'][-1]['status']='verified';save()
 time.sleep(5);after=read();assert {str(n['nm_id']):n['bids_kopecks']for n in after['nm_settings']}==target
 # Current preparation proof is separate from the original item-by-item audit.
 prep.update(status='verified',after=after,execution_key=EXEC+p['plan_id'],recovery_key=ROOT,verified_at=datetime.now(timezone.utc).isoformat());io.put(ref,prep)
 assert all(proven(items[s['id']],s)for s in e['items'])
 e.update(status='done',wb_writes=e.get('wb_writes',0)+len(record['writes']),final_composition_reconciliation=ROOT,completed_at=datetime.now(timezone.utc).isoformat());io.put(EXEC+p['plan_id'],e)
 record.update(status='verified',after=after,verified_at=datetime.now(timezone.utc).isoformat());save()
 notice=deliver_result(io,a,p,e);assert notice and notice['status']=='sent'and notice['phase']=='verified'
 a.update(status='completed',execution_key=EXEC+p['plan_id'],result_message_id=notice['message_id']);io.put(APPROVAL+'340',a)
 print(json.dumps(dict(status='verified',message_id=notice['message_id'],verified_actions=35,funding=0,starts=0)))
if __name__=='__main__':main()
