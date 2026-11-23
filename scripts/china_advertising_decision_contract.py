"""One deterministic existing-SKU decision contract for all report surfaces."""
import copy,hashlib,json
from datetime import datetime
from zoneinfo import ZoneInfo
REVISION='completed-postchange-economics-v2-budget-resume'
MSK=ZoneInfo('Europe/Moscow')
KINDS={'price','bid','added','returned','relaunch'}
def effective_launch_at(source,state):
 """A proved cash-only resume keeps the old launch; real test changes remain SKU events."""
 current=state.get('timestamps',{}).get('started')
 if not current:return None
 def instant(at):return datetime.fromisoformat(at.replace('Z','+00:00'))
 def bids(c):return {n['nm_id']:n.get('bids_kopecks',{})for n in c.get('nm_settings',[])}
 candidates=[]
 def walk(x):
  if isinstance(x,list):
   for z in x:walk(z)
  elif isinstance(x,dict):
   if x.get('status')=='verified'and str(x.get('id','')).startswith('manual-continuation:')and not x.get('selected_test'):
    before=x.get('before')if isinstance(x.get('before'),dict)else{};after=x.get('after')if isinstance(x.get('after'),dict)else{};a=after.get('timestamps',{}).get('started');b=before.get('timestamps',{}).get('started')
    if (before.get('id')==after.get('id')==state['id']and before.get('status')==11 and after.get('status')==9
        and before.get('currency')==after.get('currency')=='CNY'and bids(before)==bids(after)
        and before.get('settings',{}).get('placements')==after.get('settings',{}).get('placements')and a and b):candidates.append((a,b))
   for k in('items','groups','campaigns','payload'):walk(x.get(k))
 for rec in source.get('executions',[]):walk(rec)
 # WB started is also refreshed by a cash/status resume. An unchanged exact
 # inventory retains its proved original draft-to-active launch; SKU changes
 # still have independent verified timestamps in changed_day().
 anchors=[]
 def launch(x):
  if isinstance(x,list):
   for z in x:launch(z)
  elif isinstance(x,dict):
   before=x.get('before')if isinstance(x.get('before'),dict)else{};after=x.get('after')if isinstance(x.get('after'),dict)else{}
   if (x.get('status')=='verified'and not x.get('selected_test')
       and before.get('id')==after.get('id')==state['id']
       and before.get('status')==4 and before.get('timestamps',{}).get('started')is None
       and after.get('status')==9 and after.get('timestamps',{}).get('started')
       and before.get('currency')==after.get('currency')==state.get('currency')=='CNY'
       and bids(before)==bids(after)==bids(state)
       and after.get('settings',{}).get('placements')==state.get('settings',{}).get('placements')):
    anchors.append(after['timestamps']['started'])
   for k in('items','groups','campaigns','payload'):launch(x.get(k))
 for rec in source.get('executions',[]):launch(rec)
 if anchors:
  earliest=min(anchors,key=instant)
  if instant(earliest)<instant(current):current=earliest
 for _ in range(len(candidates)+1):
  earlier=[b for a,b in candidates if instant(a)==instant(current)and instant(b)<instant(current)]
  if not earlier:break
  current=min(earlier,key=instant)
 return current
def changed_day(source,state,nm):
 from china_advertising_v2 import history
 events=list(history(source.get('executions',[])))+list(source.get('verified_composition_changes',[]))
 for rec in source.get('experience',[]):
  event=rec.get('payload',rec);action=event.get('action',{});at=event.get('started_at')
  if action.get('kind')=='price_change'and at:
   events.extend(dict(nm=n,kind='price',at=at)for n in action.get('nm_ids',[]))
 ats=[x['at']for x in events if x.get('nm')==nm and x.get('kind')in KINDS]
 launched=effective_launch_at(source,state)
 if launched:ats.append(launched)
 days=[]
 for at in ats:
  dt=datetime.fromisoformat(at.replace('Z','+00:00'))
  if dt.tzinfo is None:raise ValueError('Verified change timestamp requires timezone')
  days.append(dt.astimezone(MSK).date().isoformat())
 return max(days,default='1970-01-01')
def normalize(bundle,source):
 """Use only full supplied days strictly after the last verified SKU change."""
 from china_advertising_v2 import daily_metrics,sums
 out=copy.deepcopy(bundle)
 if not out.get('day'):return out # Legacy context-free unit fixtures; final publication requires a dated bundle.
 day=out['day'];allowed=set(out.get('days',[]))
 raw={r['advertId']:r for b in source['batches'].values()for r in b.get('stats',[])}
 states={c['id']:c for b in source['batches'].values()for c in b['campaigns'].get('adverts',[])}
 for cp in out['campaigns']:
  state=states[cp['id']];members={n['nm_id']for n in state['nm_settings']}
  for row in cp.get('focus',[]):
   nm=row['nm']
   if nm not in members:continue
   epoch=changed_day(source,state,nm)
   ds=[d for d in raw.get(cp['id'],{}).get('days',[])if epoch<d['date'][:10]<day and d['date'][:10]in allowed]
   names=sorted({d['date'][:10]for d in ds})
   metrics=sums(daily_metrics(n)for d in ds for a in d.get('apps',[])for n in a.get('nms',[])if n['nmId']==nm)
   row['decision_window']=dict(revision=REVISION,changed_day=epoch,days=names,metrics=metrics,launch_change_day_excluded=True)
   comparison=dict(row.get('comparison')or{});comparison.update(after=metrics,to_days=names);row['comparison']=comparison
   row['pending_first_day']=not bool(names)
   if not names:row['action']=None
 return out
def comparable_action(action):
 """A repeated observation timestamp cannot change an otherwise identical proposal."""
 value=copy.deepcopy(action)
 if isinstance(value,dict) and isinstance(value.get('growth_evidence'),dict):
  for field in ('observed_at','prices_observed_at','buyout_observed_at','price_observed_at','stock_observed_at','published_stock_observed_at'):
   value['growth_evidence'].pop(field,None)
  if value.get('kind')=='ad_set_bid'and value.get('direction')=='raise'and value['growth_evidence'].get('budget_policy_revision')=='owner-20261119-reserve-advisory':
   value['growth_evidence'].pop('budget_forecast',None)
 return value

# Explicit owner instruction, 21Nov2026; applies to this campaign ID only.
OWNER_UNCHANGED_CAMPAIGNS={42088552}
def apply_owner_unchanged(bundle):
 """Keep statistics and budget proposals; suppress advertising changes only."""
 out=copy.deepcopy(bundle)
 for cp in out.get('campaigns',[]):
  if cp.get('id') not in OWNER_UNCHANGED_CAMPAIGNS:continue
  cp.update(owner_unchanged=True,direction_recommendations=['Ничего не менять.'],
   attention=[])
  for row in cp.get('focus',[]):
   row.update(action=None,decision='Ничего не менять.',reason='owner_instruction_2026-11-21')
 for section in out.get('recommendation_directions',{}).values():
  if isinstance(section,dict):
   section['rows']=[r for r in section.get('rows',[])
    if r.get('campaign_id',(r.get('action')or{}).get('campaign_id')) not in OWNER_UNCHANGED_CAMPAIGNS]
 for row in out.get('decision_contract',{}).get('rows',[]):
  if row.get('campaign_id')in OWNER_UNCHANGED_CAMPAIGNS:
   row.update(action=None,decision='Ничего не менять.',reason='owner_instruction_2026-11-21')
 return out

def finalize(io,bundle,source,minima):
 """Shared entry point for morning, midday and a cached analyst preview; no API calls."""
 from china_advertising_economic_review import apply
 from china_advertising_directions import attach
 if not bundle.get('day')or not bundle.get('days'):raise ValueError('Unified decision requires completed dated source')
 additions={(c['id'],r['nm']):copy.deepcopy(r)for c in bundle['campaigns']for r in c.get('focus',[])if (r.get('action')or{}).get('kind')=='ad_add_sku'}
 out=apply(bundle,source,minima)
 for cp in out['campaigns']:
  cp['focus']=[additions.get((cp['id'],r['nm']),r)for r in cp.get('focus',[])]
  cp['attention']=[r for r in cp['focus']if r.get('action')]
 out=apply_owner_unchanged(attach(out,source))
 rows=[];ledger_key='china_agent:advertising_decisions:v1:'+REVISION+':'+out['day']
 prior=(io.get(ledger_key)or{})if io is not None else {};ledger=copy.deepcopy(prior)
 actual_states={c['id']:c for batch in source.get('batches',{}).values() for c in batch.get('campaigns',{}).get('adverts',[])}
 for cp in out['campaigns']:
  if cp.get('owner_unchanged'):continue
  for r in cp.get('focus',[]):
   window=r.get('decision_window')
   if not window:continue
   # Timestamp refresh alone must not create a new economic decision identity.
   e=r.get('economics',{})
   facts=dict(cid=cp['id'],nm=r['nm'],window=window,cumulative=r.get('completed_exposure_guard'),status=cp.get('status'),blocker=r.get('data_blocker'),pending=r.get('pending_first_day'),current_bid=r.get('current_bid_minor'),minimum=r.get('minimum_bid_minor'),economics={k:e.get(k)for k in ('seller_price_cny','stock_free','published_stock','own_cogs_rub','buyout','sample_size','logistics_cny','commission_pct','expected_margin_before_ads_cny')})
   actual=actual_states.get(cp['id'])
   if actual is not None:
    matching=[n for n in actual.get('nm_settings',[]) if n.get('nm_id')==r['nm']]
    facts['verified_current_sku_state']=dict(present=len(matching)==1,bids=matching[0].get('bids_kopecks',{}) if len(matching)==1 else None,placements=actual.get('settings',{}).get('placements'),status=actual.get('status'))
   policy=((r.get('action')or{}).get('growth_evidence')or{}).get('budget_policy_revision')
   if policy:facts['growth_budget_policy_revision']=policy
   hh=hashlib.sha256(json.dumps(facts,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
   row=dict(campaign_id=cp['id'],nm_id=r['nm'],article=r['article'],facts_sha256=hh,decision=r.get('decision'),action=r.get('action'),decision_window=window,reason=r.get('reason'))
   key=str(cp['id'])+':'+str(r['nm'])
   if io is not None:
    old=ledger.get(key)
    if old and old.get('facts_sha256')==hh:
     if comparable_action(old.get('action'))!=comparable_action(row['action']):
      raise ValueError('Same verified facts produced conflicting recommendation: '+key)
     # Same proved facts and exact action retain the canonical wording across surfaces.
     # A presentation-only rewrite must not block every campaign's report.
     if old.get('decision')!=row['decision']:
      def instruction(text):return text.strip().split('. ',1)[0].rstrip('.') if isinstance(text,str) else None
      waiting=not row.get('action') and not old.get('action') and r.get('pending_first_day') is True and not window.get('days')
      if not waiting and (not row.get('action') or not instruction(old.get('decision')) or instruction(old.get('decision'))!=instruction(row.get('decision'))):
       raise ValueError('Same verified facts produced conflicting recommendation text: '+key)
      r['decision']=row['decision']=old.get('decision')
      r['reason']=row['reason']=old.get('reason')
    ledger[key]=row
   rows.append(row)
 for cp in out['campaigns']:cp['attention']=[r for r in cp.get('focus',[])if r.get('action')]
 if io is not None and ledger!=prior:
  if prior:io.put(ledger_key,ledger)
  else:io.create(ledger_key,ledger)
 out['decision_contract']=dict(revision=REVISION,rows=rows,deterministic=True,model_calls=0,wb_writes=0)
 return out

