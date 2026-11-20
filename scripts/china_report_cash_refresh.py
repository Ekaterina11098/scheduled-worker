"""Refresh cached report inventory and cash together; never alter a campaign."""
import copy,math
from datetime import datetime,timezone

def refresh(io,source,http,now=None):
 now=now or datetime.now(timezone.utc)
 try:
  at=datetime.fromisoformat(source['budget_balance_observed_at_iso'].replace('Z','+00:00'))
  age=(now-at).total_seconds()
  if at.tzinfo is not None and 0<=age<=20*60:return source
 except (KeyError,TypeError,ValueError):pass
 ids=sorted({c['id']for b in source['batches'].values()for c in b['campaigns']['adverts']})
 states={}
 for pos in range(0,len(ids),50):
  group=ids[pos:pos+50]
  rows=http(io,'/api/advert/v2/adverts?ids='+','.join(map(str,group))).get('adverts',[])
  if len(rows)!=len(group) or {c['id']for c in rows}!=set(group):raise ValueError('Fresh report inventory incomplete')
  states.update({c['id']:c for c in rows})
 active=[cid for cid in ids if states[cid].get('status')in(9,11)]
 cash={}
 for pos in range(0,len(active),50):
  group=active[pos:pos+50]
  rows=http(io,'/api/advert/v2/budget','POST',dict(advertIds=group)).get('adverts',[])
  if len(rows)!=len(group) or {r['advertId']for r in rows}!=set(group):raise ValueError('Fresh report balances incomplete')
  if any(type(r.get('total'))not in(int,float)or not math.isfinite(r['total'])or r['total']<0 for r in rows):raise ValueError('Fresh report balance invalid')
  cash.update({r['advertId']:r for r in rows})
 out=copy.deepcopy(source)
 for batch in out['batches'].values():
  batch['campaigns']['adverts']=[states[c['id']]for c in batch['campaigns']['adverts']]
  batch['budgets']=dict(adverts=[cash[c['id']]for c in batch['campaigns']['adverts']if c['id']in cash])
 stamp=(now if now else datetime.now(timezone.utc)).isoformat()
 out.update(budget_balance_observed_at_iso=stamp,current_state_observed_at=stamp)
 return out

def require_complete_cash_calculation(bundle):
 if not bundle.get('mandatory_campaign_format'):return
 blocked=[c['id']for c in bundle.get('campaigns',[])if c.get('status')==9 and c.get('budget_audit_state')=='data_blocked']
 if blocked:raise ValueError('Current campaign reserve calculation incomplete: '+','.join(map(str,blocked)))
