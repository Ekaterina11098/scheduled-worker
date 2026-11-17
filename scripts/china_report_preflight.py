"""Validate the actual rendered action identities before a report becomes visible."""
import copy
from datetime import datetime,timedelta,timezone
from china_loss_control import digest
def stage_restarts(io,bundle):
 result=copy.deepcopy(bundle);definitions={};routes=(io.get('china_agent:campaign_economics_routes:v1')or{}).get('campaigns',{})
 for campaign in result['campaigns']:
  action=campaign.get('financial_action')or{}
  if action.get('kind')!='recover_campaign'or action.get('keep_existing_bids')or action.get('selected_test'):continue
  evidence=action['recovery_evidence'];old=evidence['expected_bids'];zone=action['placement'];target=action['target_minor'];cid=action['campaign_id']
  if action.get('status_before')!=11 or not old:raise ValueError('Restart preparation requires an exact paused campaign')
  labels={r['nm']:r.get('article')for r in campaign.get('focus',[])}
  inputs=evidence['member_inputs'];ref='china_agent:selected_campaign_preparation:v1:'+str(cid)+':'+result['day']+':scheduled'
  new=copy.deepcopy(old);rows=[]
  for nm,bids in old.items():
   if not 0<target<bids[zone]:raise ValueError('Restart bid reduction scope changed')
   article=inputs.get(nm,{}).get('article')or labels.get(int(nm))
   if not article:raise ValueError('Restart product label unavailable before publication')
   new[nm][zone]=target
   item=dict(id='prepare-restart:'+str(cid)+':'+nm+':'+result['day'],kind='ad_set_bid',campaign_id=cid,nm_id=int(nm),article=article,placement=zone,old_minor=bids[zone],target_minor=target,status_before=11,paused_reduction_only=True,preparation_ref=ref)
   rows.append(dict(nm=int(nm),article=article,decision='Снизить '+str(bids[zone]/100)+' → '+str(target/100)+' CNY.',action=item))
  definitions[ref]=dict(status='ready_for_human_confirmation',grants_action_permission=False,campaign_id=cid,status_before=11,expected_bids=old,target_bids=new,keep_nm_ids=sorted(map(int,new)),placement=zone,target_minor=target,warehouse_role=routes.get(str(cid),{}).get('warehouse_role','msk'),expires_at=(datetime.now(timezone.utc)+timedelta(hours=20)).isoformat())
  action.update(keep_existing_bids=True,requires_preparation_key=ref,selection_family='budgets')
  evidence['expected_bids']=new
  campaign.update(focus=rows,attention=copy.deepcopy(rows),financial_recommendation='Снизить ставки до '+str(target/100)+' CNY. Пополнение и запуск — в бюджетном отчёте.',direction_recommendations=['Снизить ставки до '+str(target/100)+' CNY.'],budget_short_note='После рекламных изменений: пополнить и возобновить.')
 result['proposal_preparation_contracts']=definitions
 return result
def freeze_contracts(io,pages,preparations=None):
 for ref,template in (preparations or{}).items():
  value=copy.deepcopy(template);items=[i for p in pages for i in p['actions']if i.get('preparation_ref')==ref]
  if not items:raise ValueError('Restart preparation has no advertising actions')
  value['action_hashes']={i['id']:digest([i])for i in items};old=io.get(ref)
  if old is None:
   if not io.create(ref,value):raise ValueError('Concurrent restart preparation')
  elif old.get('action_hashes')!=value['action_hashes']or old.get('target_bids')!=value['target_bids']:raise ValueError('Restart preparation scope changed')
 seen=set();count=0
 for page in pages:
  for item in page['actions']:
   if item['id']in seen:raise ValueError('Duplicate action across report pages')
   seen.add(item['id'])
   funding=item['kind']in('topup_campaign','recover_campaign')
   if funding and (page['family']!='budgets'or type(item.get('amount_cny'))is not int or item['amount_cny']<=0):raise ValueError('Funding must be an exact amount in the budget report')
   if not funding and page['family']!='drr':raise ValueError('Advertising action placed in the budget report')
   keys=[item.get(k)for k in('manual_budget_contract','selected_test_contract','continuation_contract')if item.get(k)]
   for key in keys:
    old=io.get(key)
    if old is None:
     e=item.get('budget_evidence')or item.get('recovery_evidence')or{}
     if e.get('modeled_after_ads_cny',0)<=0 or e.get('risk_disclosed_before_confirmation')is not True:raise ValueError('Manual proposal economic/risk evidence missing')
     value=dict(status='ready_for_human_confirmation',grants_action_permission=False,maximum_funding_cny=item['amount_cny'],expires_at=(datetime.now(timezone.utc)+timedelta(hours=20)).isoformat(),action_sha256=digest([item]))
     if not io.create(key,value):raise ValueError('Concurrent proposal contract preparation')
    elif old.get('action_sha256')!=digest([item]):
     # Rendering may add the budget transport family; no economic/action field may differ.
     raw=copy.deepcopy(item);raw.pop('selection_family',None)
     if old.get('status')!='ready_for_human_confirmation'or old.get('grants_action_permission')is not False or old.get('action_sha256')!=digest([raw]):raise ValueError('Rendered proposal differs from its frozen contract')
     value=dict(old,action_sha256=digest([item]),pre_transport_action_sha256=old['action_sha256']);io.put(key,value)
    bound=io.get(key)
    if bound.get('action_sha256')!=digest([item])or bound.get('maximum_funding_cny')!=item['amount_cny']:raise ValueError('Proposal contract readback mismatch')
   dep=item.get('requires_preparation_key')
   if dep and not(io.get(dep)or{}).get('action_hashes'):raise ValueError('Advertising preparation dependency missing before publication')
   count+=1
 return dict(status='verified',action_count=count,wb_writes=0,model_calls=0)
