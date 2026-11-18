"""Prove a submitted companion package from two exact readbacks, without replaying writes."""
import copy
from datetime import datetime,timezone
AD={'ad_add_sku','ad_exclude_sku','ad_set_bid'}
def proves(item,state):
 p=state.get('package_reconciliation')or{}
 if state.get('status')!='verified'or p.get('status')!='verified'or p.get('read_only')is not True:return False
 actions=p.get('items',[]);matches=[i for i in actions if i.get('id')==item.get('id')]
 if matches!=[item]or item.get('kind')not in AD or item['id']not in p.get('submitted_ids',[]):return False
 reads=p.get('reads',[]);base=p.get('baseline')or{}
 if len(reads)!=2 or base.get('id')!=item['campaign_id']or base.get('currency')!='CNY':return False
 expected={n['nm_id']:copy.deepcopy(n)for n in base.get('nm_settings',[])}
 for i in actions:
  if i.get('campaign_id')!=base['id']or i.get('kind')not in AD or i['id']not in p.get('submitted_ids',[]):return False
  nm=i['nm_id']
  if i['kind']=='ad_exclude_sku':expected.pop(nm,None)
  elif i['kind']=='ad_set_bid':
   if nm not in expected:return False
   expected[nm]['bids_kopecks'][i['placement']]=i['target_minor']
  else:
   n=next((n for n in reads[-1].get('nm_settings',[])if n['nm_id']==nm),None)
   if not n or n.get('subject',{}).get('id')!=i['subject_id']or n['bids_kopecks'].get(i['placement'])!=i['target_minor']:return False
   expected[nm]=copy.deepcopy(n)
 for actual in reads:
  if any(actual.get(k)!=base.get(k)for k in('id','currency','status','settings'))or {n['nm_id']:n for n in actual.get('nm_settings',[])}!=expected:return False
 return state.get('after')==reads[-1]
def reconcile(items,states,rounds):
 from china_package_readback import check
 if len(rounds)!=2:raise ValueError('Two readbacks required')
 for row in rounds:
  bad,groups=check(items,states,{int(k):v for k,v in row['campaigns'].items()})
  if bad:raise ValueError('Package targets not confirmed: '+str(bad))
 byid={i['id']:i for i in items};changed=[]
 for cid,pairs in groups.items():
  if not any(s.get('status')=='uncertain'for i,s in pairs):continue
  submitted=[]
  for i,s in pairs:
   if not(s.get('already_done')or s.get('request')and s.get('submitted_at')and 'response'in s):raise ValueError('No submitted receipt for '+i['id'])
   submitted.append(i['id'])
  proof=dict(status='verified',read_only=True,items=[copy.deepcopy(i)for i,s in pairs],submitted_ids=submitted,baseline=copy.deepcopy(pairs[0][1]['before']),reads=[copy.deepcopy(r['campaigns'][str(cid)])for r in rounds])
  for i,s in pairs:
   if s.get('status')!='uncertain':continue
   old=copy.deepcopy(s);s['historical_reconciliation_state']=old;s.update(status='verified',after=proof['reads'][-1],package_reconciliation=copy.deepcopy(proof),verified_at=datetime.now(timezone.utc).isoformat(),requires_read_only_reconciliation=False)
   if not proves(i,s):raise ValueError('Invalid package proof')
   changed.append(i['id'])
 return changed
