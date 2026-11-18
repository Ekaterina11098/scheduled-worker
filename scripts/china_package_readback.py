"""Read-only whole-package validation. Never repairs or repeats mutations."""
import copy,time
from datetime import datetime,timezone

AD={'ad_add_sku','ad_exclude_sku','ad_set_bid'}
def check(items,states,current):
 byid={s['id']:s for s in states};groups={};bad={}
 for i in items:
  s=byid.get(i['id'])
  if i.get('kind') in AD and s and s.get('status')in('verified','accepted','uncertain','submitting') and s.get('before'):
   groups.setdefault(i['campaign_id'],[]).append((i,s))
 for cid,pairs in groups.items():
  initial=pairs[0][1]['before'];actual=current.get(cid)
  expected={n['nm_id']:copy.deepcopy(n)for n in initial['nm_settings']}
  for i,s in pairs:
   nm=i['nm_id'];kind=i['kind']
   if kind=='ad_exclude_sku':expected.pop(nm,None)
   elif kind=='ad_set_bid':
    if nm not in expected:bad[cid]='Bid target missing in package baseline';break
    expected[nm]['bids_kopecks'][i['placement']]=i['target_minor']
   else:
    n=next((n for n in s.get('after',{}).get('nm_settings',[])if n['nm_id']==nm),None)
    if n is None:bad[cid]='Added target has no verified member';break
    expected[nm]=copy.deepcopy(n);expected[nm]['bids_kopecks'][i['placement']]=i['target_minor']
  if cid in bad:continue
  if not actual or any(actual.get(k)!=initial.get(k)for k in('id','currency','status','settings')):
   bad[cid]='Campaign identity, status or settings changed';continue
  observed={n['nm_id']:n for n in actual['nm_settings']}
  if observed!=expected:bad[cid]='Final composition/bids differ from all submitted package targets'
 return bad,groups

def validate(items,states,campaign,pause=time.sleep):
 ids={i['campaign_id']for i in items if i.get('kind')in AD and any(s['id']==i['id']and s.get('before')and s.get('status')in('verified','accepted','uncertain','submitting')for s in states)}
 result=dict(status='verified',read_only=True,rounds=[],checked_at=datetime.now(timezone.utc).isoformat())
 for round_no in range(2):
  if round_no:pause(3)
  try:
   current={cid:campaign(cid)for cid in sorted(ids)};bad,groups=check(items,states,current)
  except Exception as ex:
   bad={cid:'Final read unavailable: '+type(ex).__name__ for cid in ids};current={}
  result['rounds'].append(dict(campaigns={str(k):v for k,v in current.items()},errors={str(k):v for k,v in bad.items()}))
  if bad:
   result['status']='uncertain'
   for s in states:
    if any(i['id']==s['id']and i.get('campaign_id')in bad for i in items)and s.get('status')in('verified','accepted','uncertain','submitting'):
     s.setdefault('historical_step_status',s['status']);s['status']='uncertain';s['final_readback_error']=next(bad[i['campaign_id']]for i in items if i['id']==s['id']);s['requires_read_only_reconciliation']=True
   break
 if result['status']=='verified':
  from china_package_proof import reconcile
  result['reconciled_item_ids']=reconcile(items,states,result['rounds'])
 return result
