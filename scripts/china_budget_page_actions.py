"""Bind every displayed budget amount without pretending a conditional reserve is a deposit."""
import copy,math
def owner_policy(io,bundle):
 out=copy.deepcopy(bundle);policy=io.get('china_agent:budget_owner_policy:v1')or{}
 for c in out['campaigns']:
  if str(c['id']) in policy.get('do_not_fund',{}):
   c['owner_budget_refused']=True;c['budget_action']=None
   c.update(budget_audit_state='owner_hold',budget_review_required=False,budget_short_note='Не пополнять: '+str(policy['do_not_fund'][str(c['id'])]))
   if str(c['id'])in out.get('budget_audit',{}):out['budget_audit'][str(c['id'])].update(status='owner_hold',review_required=False,amount_cny=None,reason=c['budget_short_note'])
 return deferred_report_context(io,out)
def page_action(c,bundle):
 """A displayed reserve is a recommendation, never an implied amount approval."""
 if bundle.get('view_only'):return None
 if (c.get('financial_action')or{}).get('kind')=='recover_campaign':return dict(copy.deepcopy(c['financial_action']),selection_family='budgets')
 if c.get('owner_budget_refused'):return None
 action=c.get('budget_action')
 return copy.deepcopy(action)if action and action.get('kind')=='topup_campaign'else None



def deferred_report_context(io,bundle):
 """Owner27Nov: show funding proposals in existing morning report, no deposit."""
 policy=io.get('china_agent:budget_deferred_report:v1')or{}
 if policy.get('status')!='active' or policy.get('day_msk')!=bundle.get('day') or policy.get('funding_authorized') is not False:return bundle
 out=copy.deepcopy(bundle)
 for c in out.get('campaigns',[]):
  if c.get('owner_budget_refused') or c.get('status')!=9:continue
  amount=c.get('budget_reserve_amount')
  if type(amount)not in(int,float)or not math.isfinite(amount)or amount<=0:continue
  original=c.get('budget_short_note')or c.get('budget_recommendation')or''
  ready=(c.get('budget_action')or{}).get('kind')=='topup_campaign'
  prefix=('Предложение к подтверждению: 'if ready else'Расчётный резерв, пока не готов к пополнению: ')+format(amount,'g')+' CNY. '
  note=prefix+original
  c.update(owner_funding_deferred_to_report=True,budget_short_note=note,budget_recommendation=note)
  if str(c['id'])in out.get('budget_audit',{}):out['budget_audit'][str(c['id'])]['reason']=note
 out['owner_funding_deferred_to_report']=dict(day_msk=policy['day_msk'],report_time_msk=policy.get('report_time_msk'),funding_authorized=False)
 return out
