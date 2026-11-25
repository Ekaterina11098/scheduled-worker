"""Exact owner-reviewed cash reserve publication. Not an economic approval or auto funding."""
import copy
from datetime import datetime, timezone
ROOT='china_agent:owner_budget_publish:2026-11-25:r1'
AMOUNTS={40933588:3150,41155909:200,41270309:350,41298169:350,41325622:100,41332083:250,42088552:400}

def check(io,item,before):
 from china_loss_control import digest
 cid=item['campaign_id'];key=ROOT+':contract:'+str(cid)
 record=io.get(key)or{}
 frozen=next((x for x in getattr(io,'daily_report_plan',{}).get('items',[])if x.get('id')==item.get('id')),None)
 request=io.get(ROOT+':owner_request')or{}
 if (cid not in AMOUNTS or item.get('owner_cash25_contract')!=key or not frozen
     or record.get('status')!='ready_for_human_confirmation' or record.get('grants_action_permission')is not False
     or request.get('status')!='approved_for_publication_only' or request.get('total_cny')!=4800
     or record.get('action_sha256')!=digest([frozen]) or record.get('maximum_funding_cny')!=AMOUNTS[cid]
     or item.get('amount_cny')!=AMOUNTS[cid] or record.get('campaign_id')!=cid
     or not record.get('risk_disclosed_before_confirmation') or record.get('period_to')!='2026-11-24'):
  raise ValueError('Exact reviewed cash proposal changed')
 if not getattr(io,'daily_report_approval',{}).get('sender_id'):
  raise ValueError('Human report confirmation required')
 if before['id']!=cid or before['status']!=9 or before['currency']!='CNY':
  raise ValueError('Reviewed active CNY campaign changed; no automatic restart')
 if (io.get('china_agent:budget_owner_policy:v1')or{}).get('do_not_fund',{}).get(str(cid)):
  raise ValueError('Owner funding hold')
 e=copy.deepcopy(frozen['budget_evidence'])
 actual={str(n['nm_id']):n['bids_kopecks']for n in before['nm_settings']}
 if actual!=e['expected_bids']:
  from china_confirmed_funding_context import reconcile
  e=reconcile(io,e,before)
 if item!=frozen:
  derived=copy.deepcopy(frozen);derived.update(budget_evidence=e,nm_ids=sorted(map(int,actual)))
  if item!=derived:raise ValueError('Cash proposal differs from verified companion reconciliation')
 verified=set(e.get('confirmed_state_reconciliation',{}).get('verified_item_ids',[]))
 for required in record.get('required_actions',[]):
  nm=str(required['nm_id'])
  if required['id']not in verified:raise ValueError('Сначала подтвердите и дождитесь проверки изменений рекламного отчёта по РК '+str(cid))
  if required['kind']=='ad_exclude_sku'and nm in actual:raise ValueError('Required exclusion not verified')
  if required['kind']=='ad_set_bid'and actual.get(nm,{}).get(required['placement'])!=required['target_minor']:
   raise ValueError('Required bid reduction not verified')
 return record,e

def validate(io,item,before):
 record,e=check(io,item,before)
 # The owner reviews a cash reserve with disclosed risk, not a fabricated positive model.
 # Fresh prices and the exact verified composition still have to match the visible plan.
 from china_morning_readiness import current_prices
 ids=sorted(n['nm_id']for n in before['nm_settings']);prices=current_prices(io,ids)
 if {r['nm_id']for r in prices['rows']}!=set(ids):raise ValueError('Exact reviewed price coverage missing')
 for r in prices['rows']:
  old=e['member_inputs'].get(str(r['nm_id']))or{}
  if r.get('article')!=old.get('article')or r.get('seller_price')!=old.get('price'):
   raise ValueError('Price or product changed after cash report: '+str(r.get('article')))
 return dict(status='owner_reviewed_cash_reserve',profit_proven=False,
             economic_risk_disclosed=True,amount_cny=item['amount_cny'],
             verified_companion_items=e.get('confirmed_state_reconciliation',{}).get('verified_item_ids',[]))

