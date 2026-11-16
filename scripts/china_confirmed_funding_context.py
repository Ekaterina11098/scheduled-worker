"""Reconcile only WB-verified changes selected in the companion report by the same human."""
import copy,hashlib
def reconcile(io,evidence,before):
 from china_loss_control import PLAN,APPROVAL
 from china_execution_notice import proven
 p=getattr(io,'daily_report_plan',{});a=getattr(io,'daily_report_approval',{})
 def base(v):return v.get('report_generation','').removesuffix('-'+v.get('family',''))
 pointer=io.get('china_agent:daily_ad_current_report:v1:drr')or{};parent=io.get(PLAN+pointer.get('plan_id',''))or{}
 if not a.get('sender_id')or not base(p)or parent.get('period_to')!=p.get('period_to'):raise ValueError('Composition changed outside the confirmed report pair')
 if base(parent)!=base(p):
  # A corrected DRR report may retain its message and change generation while
  # the budget report remains current. Require BOTH exact current parent plans,
  # identities and hashes; the same-human verified chain below is still mandatory.
  bp=io.get('china_agent:daily_ad_current_report:v1:budgets')or{}
  root_id=p.get('parent_plan_id')or p.get('plan_id')
  budget=io.get(PLAN+str(root_id))or{}
  if (p.get('family')!='budgets'or parent.get('family')!='drr'
      or bp.get('plan_id')!=root_id or budget.get('plan_id')!=root_id
      or budget.get('plan_sha256')!=(p.get('parent_plan_sha256')or p.get('plan_sha256'))
      or budget.get('report_generation')!=p.get('report_generation')
      or budget.get('period_to')!=parent.get('period_to')
      or not budget.get('report_message_ids')or not parent.get('report_message_ids')
      or budget.get('chat_id')!=parent.get('chat_id')or budget.get('bot_id')!=parent.get('bot_id')
      or budget.get('chat_id')!=-1004342917488 or budget.get('bot_id')!=8780468043):
   raise ValueError('Composition changed outside the confirmed report pair')
 token=hashlib.sha256((parent['plan_id']+':'+parent['plan_sha256']+':drr').encode()).hexdigest()[:24]+'-'+str(a['sender_id'])
 c=io.get('china_agent:report_buttons:v1:confirmation:'+token)or{}
 if c.get('status')!='confirmed'or c.get('sender_id')!=a['sender_id']or c.get('plan_sha256')!=parent['plan_sha256']:raise ValueError('Companion human confirmation missing')
 child=io.get(PLAN+parent['plan_id']+'-buttons-'+token)or{};approval=io.get(APPROVAL+str(c.get('job_id')))or{}
 if child.get('selected_ids',c.get('selected_ids'))!=c.get('selected_ids')or approval.get('plan_id')!=child.get('plan_id')or approval.get('sender_id')!=a['sender_id']or approval.get('status')not in('approved','completed'):raise ValueError('Companion approval changed')
 key='china_agent:daily_ad_execution:v2:'+child['plan_id'];execution=io.get(key)or{}
 if execution.get('plan_sha256')!=child.get('plan_sha256'):raise ValueError('Companion execution hash missing')
 items={i['id']:i for i in child.get('items',[])if i['campaign_id']==before['id']}
 states=[s for s in execution.get('items',[])if s['id']in items]
 if not items or len(states)!=len(items)or any(not proven(items[s['id']],s)for s in states):raise ValueError('Companion campaign changes not all WB verified')
 out=copy.deepcopy(evidence);expected=copy.deepcopy(out['expected_bids'])
 def bids(c):return {str(n['nm_id']):n['bids_kopecks']for n in c['nm_settings']}
 for state in states:
  item=items[state['id']]
  # Individual receipts are verified above. WB reads can lag across sequential
  # mutations; derive the cumulative approved target instead of treating each
  # intermediate before-image as the next authoritative inventory.
  nm=str(item.get('nm_id'))
  if item['kind']=='ad_set_bid':
   if nm not in expected:raise ValueError('Approved bid target absent from original funding composition')
   expected[nm][item['placement']]=item['target_minor']
  elif item['kind']=='ad_exclude_sku':expected.pop(nm,None)
  elif item['kind']=='ad_add_sku':expected[nm]=copy.deepcopy(bids(state['after'])[nm])
  else:raise ValueError('Unsupported companion composition operation')
  if item['kind']=='ad_add_sku':
   e=item.get('growth_evidence')or{};nm=str(item['nm_id'])
   needed=['seller_price_cny','own_cogs_rub','fx_rub_per_cny','stock_free','published_stock']
   if any(type(e.get(k))not in(int,float)for k in needed)or e.get('expected_margin_before_ads_cny',0)<=0:raise ValueError('Confirmed addition economics missing')
   out['member_inputs'][nm]=dict(article=item['article'],price=e['seller_price_cny'],cost=e['own_cogs_rub'],buyout=e.get('buyout'),fx=e['fx_rub_per_cny'],stock_free=e['stock_free'],published_stock=e['published_stock'])
 if expected!=bids(before):raise ValueError('Current composition is not the exact verified companion result')
 out['expected_bids']=expected
 out['confirmed_state_reconciliation']=dict(budget_parent_plan_id=p.get('parent_plan_id')or p.get('plan_id'),companion_parent_plan_id=parent['plan_id'],companion_parent_plan_sha256=parent['plan_sha256'],execution_key=key,verified_item_ids=list(items),original_report_model_unchanged=True,no_new_attributed_profit_credit=True)
 return out
